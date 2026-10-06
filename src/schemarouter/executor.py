from __future__ import annotations

import asyncio
import inspect
import math
import threading
import time
from collections.abc import AsyncIterator, Awaitable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from .authorization import (
    AuthorizationPolicy,
    DataScopeDecision,
    _current_principal_context,
    _data_scope_execution_context,
)
from .errors import (
    ApprovalDeniedError,
    BindingDriftError,
    ExecutionBudgetExceededError,
    ExecutionError,
    ExecutionHookError,
    IndeterminateInvocationError,
    InvocationUnavailableError,
    NonRetryableInvocationError,
    PlanValidationError,
    PolicyViolationError,
    PostInvocationHookError,
    RegistrationError,
    SchemaDriftError,
    SchemaValidationError,
)
from .evidence import available_evidence, field_evidence_status, global_evidence_status
from .hooks import ExecutionHooks
from .models import (
    EndpointSpec,
    ExecutionPlan,
    ResultFieldContract,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .policy import ApprovalCallback, ExecutionPolicy, is_remote_tool
from .registry import (
    ToolRegistry,
    replace_if_current,
    unregister_if_current,
    update_many_if_current,
)
from .runs import ExecutionBudget, RetryPolicy
from .validation import (
    canonical_field_value_schema,
    effective_input_schema,
    effective_output_schema,
    json_schema_types,
    projected_output_schema,
    validate_json_schema_value,
)

_MISSING = object()


class EndpointInvoker(Protocol):
    def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]: ...


class CallAwareEndpointInvoker(Protocol):
    def invoke_call(self, call: ToolCall) -> Any | Awaitable[Any]: ...


BoundEndpointInvoker = EndpointInvoker | CallAwareEndpointInvoker


@dataclass(frozen=True)
class _BindingSnapshot:
    invoker: BoundEndpointInvoker | None
    fingerprint: str | None
    offload_sync: bool
    generation: int | None


@dataclass
class ExecutionBudgetTracker:
    budget: ExecutionBudget
    started: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    attempts: int = 0
    remote_attempts: int = 0
    cost_units: float = 0.0
    per_tool_calls: dict[str, int] = field(default_factory=dict)
    _reservation_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        repr=False,
        compare=False,
    )

    def _check_elapsed(self, *, stage: str | None = None) -> None:
        limit = self.budget.max_elapsed_seconds
        if limit is not None and time.monotonic() - self.started >= limit:
            suffix = f" during {stage}" if stage else ""
            raise ExecutionBudgetExceededError(
                f"execution exceeded max_elapsed_seconds={limit}{suffix}"
            )

    def remaining_seconds(self, *, stage: str | None = None) -> float | None:
        limit = self.budget.max_elapsed_seconds
        if limit is None:
            return None
        remaining = limit - (time.monotonic() - self.started)
        if remaining <= 0:
            self._check_elapsed(stage=stage)
        return max(remaining, 0.0)

    async def wait_awaitable(
        self,
        awaitable: Awaitable[Any],
        *,
        stage: str,
    ) -> Any:
        """Await trusted async work without allowing it to outlive the elapsed budget."""
        remaining = self.remaining_seconds(stage=stage)
        if remaining is None:
            value = await awaitable
            self._check_elapsed(stage=stage)
            return value
        try:
            value = await asyncio.wait_for(awaitable, timeout=remaining)
        except asyncio.TimeoutError as exc:
            limit = self.budget.max_elapsed_seconds
            raise ExecutionBudgetExceededError(
                f"execution exceeded max_elapsed_seconds={limit} during {stage}"
            ) from exc
        self._check_elapsed(stage=stage)
        return value

    def after_attempt(self) -> None:
        self._check_elapsed()

    async def wait_backoff(self, delay: float) -> None:
        """Wait between attempts without sleeping past the wall-clock budget."""
        if delay <= 0:
            return

        remaining = self.remaining_seconds(stage="retry backoff")
        if remaining is None:
            await asyncio.sleep(delay)
            return

        if delay >= remaining:
            await asyncio.sleep(remaining)
            raise ExecutionBudgetExceededError(
                "execution exceeded "
                f"max_elapsed_seconds={self.budget.max_elapsed_seconds} during retry backoff"
            )

        await asyncio.sleep(delay)
        self._check_elapsed(stage="retry backoff")

    async def before_call(self, call: ToolCall) -> None:
        async with self._reservation_lock:
            self._check_elapsed()
            next_total = self.tool_calls + 1
            if (
                self.budget.max_tool_calls is not None
                and next_total > self.budget.max_tool_calls
            ):
                raise ExecutionBudgetExceededError(
                    f"execution would exceed max_tool_calls={self.budget.max_tool_calls}"
                )

            tool_total = self.per_tool_calls.get(call.tool, 0) + 1
            tool_limit = self.budget.per_tool_calls.get(call.tool)
            if tool_limit is not None and tool_total > tool_limit:
                raise ExecutionBudgetExceededError(
                    f"execution would exceed per_tool_calls[{call.tool!r}]={tool_limit}"
                )

            self.tool_calls = next_total
            self.per_tool_calls[call.tool] = tool_total

    async def before_attempt(self, call: ToolCall, tool: ToolSpec) -> None:
        async with self._reservation_lock:
            self._check_elapsed()
            next_attempts = self.attempts + 1
            if (
                self.budget.max_attempts is not None
                and next_attempts > self.budget.max_attempts
            ):
                raise ExecutionBudgetExceededError(
                    f"execution would exceed max_attempts={self.budget.max_attempts}"
                )

            remote = is_remote_tool(tool)
            next_remote = self.remote_attempts + (1 if remote else 0)
            if (
                self.budget.max_remote_attempts is not None
                and next_remote > self.budget.max_remote_attempts
            ):
                raise ExecutionBudgetExceededError(
                    "execution would exceed "
                    f"max_remote_attempts={self.budget.max_remote_attempts}"
                )

            operation = f"{call.tool}.{call.endpoint}"
            cost = self.budget.cost_units.get(
                operation,
                self.budget.cost_units.get(
                    call.tool,
                    self.budget.cost_units.get("*", 0.0),
                ),
            )
            next_cost = self.cost_units + cost
            if (
                self.budget.max_cost_units is not None
                and next_cost > self.budget.max_cost_units
            ):
                raise ExecutionBudgetExceededError(
                    f"execution would exceed max_cost_units={self.budget.max_cost_units}"
                )

            self.attempts = next_attempts
            self.remote_attempts = next_remote
            self.cost_units = next_cost


class RegistryExecutor:
    """Executes validated plans using caller-supplied trusted invokers."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        policy: ExecutionPolicy | None = None,
        authorization_policy: AuthorizationPolicy | None = None,
        approval_callback: ApprovalCallback | None = None,
        hooks: ExecutionHooks | None = None,
        unavailable_cooldown_seconds: float = 30.0,
    ) -> None:
        if (
            not isinstance(unavailable_cooldown_seconds, (int, float))
            or isinstance(unavailable_cooldown_seconds, bool)
            or not math.isfinite(float(unavailable_cooldown_seconds))
            or unavailable_cooldown_seconds < 0
        ):
            raise ValueError("unavailable_cooldown_seconds must be a finite non-negative number")
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self.authorization_policy = authorization_policy
        self.approval_callback = approval_callback
        self.hooks = hooks or ExecutionHooks()
        self.unavailable_cooldown_seconds = float(unavailable_cooldown_seconds)
        self._runtime_state_lock = threading.RLock()
        self._binding_generation = 0
        self._invokers: dict[str, BoundEndpointInvoker] = {}
        self._binding_fingerprints: dict[str, str] = {}
        self._binding_offload_sync: dict[str, bool] = {}
        self._binding_generations: dict[str, int] = {}
        self._inflight_offloaded_sync: set[asyncio.Future[Any]] = set()
        self._unavailable_until: dict[tuple[str, str, str], float] = {}

    def _binding_snapshot(self, tool_key: str) -> _BindingSnapshot:
        with self._runtime_state_lock:
            return _BindingSnapshot(
                invoker=self._invokers.get(tool_key),
                fingerprint=self._binding_fingerprints.get(tool_key),
                offload_sync=self._binding_offload_sync.get(tool_key, False),
                generation=self._binding_generations.get(tool_key),
            )

    def _store_binding(
        self,
        tool_key: str,
        invoker: BoundEndpointInvoker,
        fingerprint: str,
        offload_sync: bool,
    ) -> int:
        with self._runtime_state_lock:
            self._binding_generation += 1
            generation = self._binding_generation
            self._invokers[tool_key] = invoker
            self._binding_fingerprints[tool_key] = fingerprint
            self._binding_offload_sync[tool_key] = offload_sync
            self._binding_generations[tool_key] = generation
            return generation

    def _remove_binding_locked(self, tool_key: str) -> None:
        self._invokers.pop(tool_key, None)
        self._binding_fingerprints.pop(tool_key, None)
        self._binding_offload_sync.pop(tool_key, None)
        self._binding_generations.pop(tool_key, None)

    def _remove_binding_if_generation(
        self,
        tool_key: str,
        generation: int,
    ) -> bool:
        with self._runtime_state_lock:
            if self._binding_generations.get(tool_key) != generation:
                return False
            self._remove_binding_locked(tool_key)
            return True

    def _restore_binding_if_generation(
        self,
        tool_key: str,
        generation: int,
        previous: _BindingSnapshot,
    ) -> bool:
        with self._runtime_state_lock:
            if self._binding_generations.get(tool_key) != generation:
                return False
            if previous.invoker is None or previous.fingerprint is None:
                self._remove_binding_locked(tool_key)
                return True

            self._binding_generation += 1
            restored_generation = self._binding_generation
            self._invokers[tool_key] = previous.invoker
            self._binding_fingerprints[tool_key] = previous.fingerprint
            self._binding_offload_sync[tool_key] = previous.offload_sync
            self._binding_generations[tool_key] = restored_generation
            return True

    def _current_access_key(
        self,
        tool_key: str,
        endpoint: str,
    ) -> tuple[str, str, str]:
        tool = self.registry.get(tool_key)
        tool.endpoint(endpoint)
        return tool_key, endpoint, tool.fingerprint

    def _purge_access_cooldowns_locked(self, tool_key: str, endpoint: str) -> None:
        stale = [
            key
            for key in self._unavailable_until
            if key[0] == tool_key and key[1] == endpoint
        ]
        for key in stale:
            self._unavailable_until.pop(key, None)

    def _purge_access_cooldowns(self, tool_key: str, endpoint: str) -> None:
        with self._runtime_state_lock:
            self._purge_access_cooldowns_locked(tool_key, endpoint)

    def mark_access_unavailable(
        self,
        tool_key: str,
        endpoint: str,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        cooldown = (
            self.unavailable_cooldown_seconds
            if cooldown_seconds is None
            else float(cooldown_seconds)
        )
        if not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError("cooldown_seconds must be a finite non-negative number")
        key = self._current_access_key(tool_key, endpoint)
        with self._runtime_state_lock:
            self._purge_access_cooldowns_locked(tool_key, endpoint)
            self._unavailable_until[key] = time.monotonic() + cooldown

    def _mark_access_available_for_contract(
        self,
        tool_key: str,
        endpoint: str,
        tool_fingerprint: str,
    ) -> None:
        with self._runtime_state_lock:
            self._unavailable_until.pop(
                (tool_key, endpoint, tool_fingerprint),
                None,
            )

    def _mark_access_unavailable_for_contract(
        self,
        tool_key: str,
        endpoint: str,
        tool_fingerprint: str,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        cooldown = (
            self.unavailable_cooldown_seconds
            if cooldown_seconds is None
            else float(cooldown_seconds)
        )
        if not math.isfinite(cooldown) or cooldown < 0:
            raise ValueError("cooldown_seconds must be a finite non-negative number")
        with self._runtime_state_lock:
            self._purge_access_cooldowns_locked(tool_key, endpoint)
            self._unavailable_until[
                (tool_key, endpoint, tool_fingerprint)
            ] = time.monotonic() + cooldown

    def mark_access_available(self, tool_key: str, endpoint: str) -> None:
        self._current_access_key(tool_key, endpoint)
        with self._runtime_state_lock:
            self._purge_access_cooldowns_locked(tool_key, endpoint)

    def is_access_available_for_contract(
        self,
        tool_key: str,
        endpoint: str,
        tool_fingerprint: str,
    ) -> bool:
        key = (tool_key, endpoint, tool_fingerprint)
        with self._runtime_state_lock:
            until = self._unavailable_until.get(key)
            if until is None:
                return True
            if time.monotonic() >= until:
                self._unavailable_until.pop(key, None)
                return True
            return False

    def is_access_available(self, tool_key: str, endpoint: str) -> bool:
        key = self._current_access_key(tool_key, endpoint)
        with self._runtime_state_lock:
            until = self._unavailable_until.get(key)
            if until is None:
                return True
            if time.monotonic() >= until:
                self._unavailable_until.pop(key, None)
                return True
            return False

    def unavailable_access_paths(self) -> tuple[tuple[str, str], ...]:
        now = time.monotonic()
        active: list[tuple[str, str]] = []
        stale: list[tuple[tuple[str, str, str], float]] = []

        with self._runtime_state_lock:
            cooldowns = tuple(self._unavailable_until.items())

        for key, until in cooldowns:
            tool_key, endpoint, fingerprint = key
            if now >= until:
                stale.append((key, until))
                continue
            try:
                current = self.registry.get(tool_key)
                current.endpoint(endpoint)
            except KeyError:
                stale.append((key, until))
                continue
            if current.fingerprint != fingerprint:
                stale.append((key, until))
                continue
            active.append((tool_key, endpoint))

        with self._runtime_state_lock:
            for key, observed_until in stale:
                if self._unavailable_until.get(key) == observed_until:
                    self._unavailable_until.pop(key, None)
        return tuple(sorted(active))

    def binding_status_for_contract(
        self,
        tool_key: str,
        tool_fingerprint: str,
    ) -> str:
        binding = self._binding_snapshot(tool_key)
        if binding.invoker is None:
            return "unbound"
        if binding.fingerprint != tool_fingerprint:
            return "stale"
        return "ready"

    def is_binding_ready_for_contract(
        self,
        tool_key: str,
        tool_fingerprint: str,
    ) -> bool:
        return self.binding_status_for_contract(tool_key, tool_fingerprint) == "ready"

    def ordered_available_fallback_chain(
        self,
        call: ToolCall,
        alternatives: list[ToolCall] | tuple[ToolCall, ...],
    ) -> list[ToolCall]:
        self.validate_fallback_chain(call, alternatives)
        chain = [call, *alternatives]
        executable: list[ToolCall] = []
        bound_candidate_seen = False

        for index, candidate in enumerate(chain):
            try:
                self._validated_call_contract(candidate)
            except PlanValidationError:
                if index == 0:
                    raise
                # Optional alternatives that no longer satisfy their schema/policy contract are
                # pruned before the primary executes rather than blocking an otherwise valid call.
                continue

            if candidate.tool_fingerprint is None:
                if index == 0:
                    raise PlanValidationError(
                        "tool_fingerprint is required for automatic fallback execution"
                    )
                continue

            binding_status = self.binding_status_for_contract(
                candidate.tool,
                candidate.tool_fingerprint,
            )
            if binding_status != "ready":
                continue

            bound_candidate_seen = True
            if not self.is_access_available_for_contract(
                candidate.tool,
                candidate.endpoint,
                candidate.tool_fingerprint,
            ):
                continue

            executable.append(candidate)

        if executable:
            return executable
        if bound_candidate_seen:
            raise InvocationUnavailableError(
                "all executable precompiled access paths are temporarily unavailable"
            )
        raise ExecutionError(
            "no currently bound executable access path exists in the precompiled fallback chain"
        )

    def bind(
        self,
        tool_key: str,
        invoker: BoundEndpointInvoker,
        *,
        expected_fingerprint: str | None = None,
        offload_sync: bool = False,
    ) -> int:
        """Bind an invoker, optionally pinned to the exact contract it was built for.

        Callers that construct an invoker from a particular ToolSpec must pass that
        spec's fingerprint. If the registry moved before binding, refuse before
        storing the invoker rather than blessing it for an unrelated contract.
        """
        if not isinstance(offload_sync, bool):
            raise TypeError("offload_sync must be a bool")
        tool = self.registry.get(tool_key)
        if (
            expected_fingerprint is not None
            and tool.fingerprint != expected_fingerprint
        ):
            raise BindingDriftError(
                f"cannot bind {tool_key!r}: registry contract changed; expected "
                f"{expected_fingerprint!r}, found {tool.fingerprint!r}"
            )
        fingerprint = expected_fingerprint or tool.fingerprint
        return self._store_binding(
            tool_key,
            invoker,
            fingerprint,
            offload_sync,
        )

    def publish_bound_tool(
        self,
        tool: ToolSpec,
        invoker: BoundEndpointInvoker,
        *,
        replace: bool = False,
        expected_fingerprint: str | None = None,
        expected_version: int | None = None,
        offload_sync: bool = False,
    ) -> str:
        """Publish one registry contract and trusted binding as one logical transition.

        The registry write remains the concurrency authority. If binding fails, rollback is
        attempted only while the registry still contains the exact contract/version published by
        this call. A concurrent writer therefore causes a fail-closed outcome instead of being
        overwritten by rollback.
        """

        if not isinstance(offload_sync, bool):
            raise TypeError("offload_sync must be a bool")

        registry = self.registry
        base_version = registry.version if expected_version is None else expected_version
        try:
            previous_tool = registry.get(tool.key)
        except KeyError:
            previous_tool = None

        # A failed bind must always be rollback-capable before mutating the registry. Built-in
        # registries provide these stronger CAS interfaces; weaker custom registries fail closed.
        if previous_tool is None:
            if not callable(getattr(registry, "update_many_if_version", None)):
                raise RegistrationError(
                    "atomic bound registration requires version-guarded batch registration"
                )
            if not callable(getattr(registry, "unregister_if_fingerprint", None)):
                raise RegistrationError(
                    "atomic bound registration requires unregister-if-fingerprint rollback"
                )
        elif not callable(getattr(registry, "replace_if_fingerprint", None)):
            raise RegistrationError(
                "atomic bound replacement requires replace-if-fingerprint rollback"
            )

        previous_binding = self._binding_snapshot(tool.key)

        if previous_tool is None:
            keys = update_many_if_current(
                registry,
                (tool,),
                expected_version=base_version,
                replace=False,
            )
            if len(keys) != 1:
                raise RegistrationError(
                    "atomic bound registration returned an invalid tool-key count"
                )
            key = keys[0]
        else:
            if not replace:
                # Use the version-guarded path even for the expected duplicate failure so no
                # weaker register-then-rollback path is introduced.
                update_many_if_current(
                    registry,
                    (tool,),
                    expected_version=base_version,
                    replace=False,
                )
                raise RegistrationError(f"tool {tool.key!r} is already registered")
            key = replace_if_current(
                registry,
                tool,
                expected_fingerprint=(
                    expected_fingerprint
                    if expected_fingerprint is not None
                    else previous_tool.fingerprint
                ),
                expected_version=base_version,
            )

        published_version = base_version + 1

        published_generation: int | None = None

        try:
            published_generation = self.bind(
                key,
                invoker,
                expected_fingerprint=tool.fingerprint,
                offload_sync=offload_sync,
            )

            # Detect a registry writer that raced after the binding snapshot was published.
            if registry.version != published_version:
                raise BindingDriftError(
                    f"registry changed concurrently while publishing binding for {key!r}"
                )
            if registry.get(key).fingerprint != tool.fingerprint:
                raise BindingDriftError(
                    f"tool {key!r} changed concurrently while publishing its binding"
                )
        except Exception:
            try:
                if previous_tool is None:
                    unregister_if_current(
                        registry,
                        key,
                        expected_fingerprint=tool.fingerprint,
                        expected_version=published_version,
                    )
                else:
                    replace_if_current(
                        registry,
                        previous_tool,
                        expected_fingerprint=tool.fingerprint,
                        expected_version=published_version,
                    )
            except Exception as rollback_exc:
                if published_generation is not None:
                    self._remove_binding_if_generation(
                        key,
                        published_generation,
                    )
                raise BindingDriftError(
                    f"binding publication for {key!r} failed and registry rollback "
                    "could not be completed without overwriting concurrent state"
                ) from rollback_exc

            if published_generation is not None:
                self._restore_binding_if_generation(
                    key,
                    published_generation,
                    previous_binding,
                )
            raise

        return key

    def _bound_invoker_for_contract(
        self,
        tool_key: str,
        tool_fingerprint: str,
    ) -> BoundEndpointInvoker | None:
        """Return trusted process-local binding only when it matches one exact contract.

        This is an internal lifecycle hook for operations such as transport-native schema
        refresh. It deliberately does not expose invokers through SchemaRouter's public API.
        """
        binding = self._binding_snapshot(tool_key)
        if (
            binding.invoker is None
            or binding.fingerprint != tool_fingerprint
        ):
            return None
        return binding.invoker

    def _bound_binding_for_contract(
        self,
        tool_key: str,
        tool_fingerprint: str,
    ) -> tuple[BoundEndpointInvoker, bool] | None:
        """Return one current trusted binding plus its sync-offload mode.

        This package-internal lifecycle hook lets SchemaRouter roll back a failed
        contract rebind without exposing live invokers through the public API.
        """
        binding = self._binding_snapshot(tool_key)
        if (
            binding.invoker is None
            or binding.fingerprint != tool_fingerprint
        ):
            return None
        return binding.invoker, binding.offload_sync

    def restamp_binding(self, tool_key: str, expected_fingerprint: str) -> bool:
        """Re-point an existing binding at a fingerprint the caller already validated.

        Used only after trusted local code amends a contract in a way that
        `amendment.validate_amendment` accepted. The invoker object is neither
        accepted nor returned, so the caller never handles a live transport.

        `expected_fingerprint` must be the fingerprint of the amendment that was
        actually validated. The current registry entry is re-read and compared
        against it rather than trusted outright: if some other writer replaced
        the registered spec between validation and this call (a concurrent
        thread, or another process on a shared registry), the fingerprints will
        no longer match and the binding is left untouched. Re-reading the
        registry's fingerprint and stamping it unconditionally would let a
        binding go "ready" for a contract that never passed validation.
        """
        previous = self._binding_snapshot(tool_key)
        if previous.invoker is None or previous.generation is None:
            return False
        if self.registry.get(tool_key).fingerprint != expected_fingerprint:
            return False

        with self._runtime_state_lock:
            if self._binding_generations.get(tool_key) != previous.generation:
                return False
            self._binding_generation += 1
            restamped_generation = self._binding_generation
            self._binding_fingerprints[tool_key] = expected_fingerprint
            self._binding_generations[tool_key] = restamped_generation

        if self.registry.get(tool_key).fingerprint != expected_fingerprint:
            self._restore_binding_if_generation(
                tool_key,
                restamped_generation,
                previous,
            )
            return False
        return True

    def unbind(self, tool_key: str) -> None:
        with self._runtime_state_lock:
            self._remove_binding_locked(tool_key)

    def _track_offloaded_sync_task(self, task: asyncio.Future[Any]) -> None:
        """Keep an offloaded worker task alive until its thread-backed call finishes."""

        self._inflight_offloaded_sync.add(task)

        def cleanup(done: asyncio.Future[Any]) -> None:
            self._inflight_offloaded_sync.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        task.add_done_callback(cleanup)

    async def _await_side_effecting_offloaded_sync(
        self,
        awaitable: Awaitable[Any],
        *,
        tracker: ExecutionBudgetTracker,
        call: ToolCall,
    ) -> Any:
        """Await a sync mutation without pretending an in-flight worker was cancelled."""

        # Check the trusted deadline before scheduling the worker so a budget that is already
        # exhausted remains a normal pre-invocation budget failure.
        remaining = tracker.remaining_seconds(stage="invocation")
        task = asyncio.ensure_future(awaitable)
        self._track_offloaded_sync_task(task)

        try:
            if remaining is None:
                value = await asyncio.shield(task)
            else:
                value = await asyncio.wait_for(asyncio.shield(task), timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise IndeterminateInvocationError(
                "offloaded synchronous invocation outcome is indeterminate after deadline "
                f"for {call.tool}.{call.endpoint}; the worker may still complete"
            ) from exc
        except asyncio.CancelledError as exc:
            raise IndeterminateInvocationError(
                "offloaded synchronous invocation outcome is indeterminate after cancellation "
                f"for {call.tool}.{call.endpoint}; the worker may still complete"
            ) from exc

        tracker._check_elapsed(stage="invocation")
        return value

    def purge_tool_runtime_state(self, tool_key: str) -> None:
        """Forget trusted binding and bounded availability state for one tool."""

        with self._runtime_state_lock:
            self._remove_binding_locked(tool_key)
            stale = [
                key
                for key in self._unavailable_until
                if key[0] == tool_key
            ]
            for key in stale:
                self._unavailable_until.pop(key, None)

    def bound_keys(self) -> tuple[str, ...]:
        """Return live trusted-invoker keys without exposing invoker objects."""
        with self._runtime_state_lock:
            return tuple(sorted(self._invokers))

    def binding_states(self) -> dict[str, str]:
        """Return privacy-safe binding readiness for registered and orphaned bindings."""

        with self._runtime_state_lock:
            bindings = {
                key: (self._invokers.get(key), self._binding_fingerprints.get(key))
                for key in set(self._invokers) | set(self._binding_fingerprints)
            }

        states: dict[str, str] = {}
        registry_keys = set(self.registry.keys())
        binding_keys = set(bindings)

        for key in sorted(registry_keys | binding_keys):
            if key not in registry_keys:
                states[key] = "orphaned"
                continue
            tool = self.registry.get(key)
            invoker, fingerprint = bindings.get(key, (None, None))
            if invoker is None:
                states[key] = "unbound"
            elif fingerprint != tool.fingerprint:
                states[key] = "stale"
            else:
                states[key] = "ready"
        return states

    def _validated_call_contract(
        self,
        call: ToolCall,
    ) -> tuple[ToolSpec, EndpointSpec]:
        try:
            tool = self.registry.get(call.tool)
            endpoint = tool.endpoint(call.endpoint)
        except KeyError as exc:
            message = f"unknown tool/endpoint: {call.tool}.{call.endpoint}"
            raise PlanValidationError(message) from exc

        if call.tool_fingerprint is None and (
            tool.remote
            or bool(tool.execution_metadata)
            or bool(endpoint.execution_metadata)
        ):
            raise PlanValidationError(
                "tool_fingerprint is required for remote or runtime-sensitive "
                f"operation {call.tool}.{call.endpoint}; replan before execution"
            )

        if call.tool_fingerprint is not None and tool.fingerprint != call.tool_fingerprint:
            raise SchemaDriftError(
                f"tool contract changed for {call.tool!r}; replan before execution"
            )

        if endpoint.fingerprint != call.schema_fingerprint:
            raise SchemaDriftError(
                f"schema changed for {call.tool}.{call.endpoint}; replan before execution"
            )

        declared_parameters = {parameter.name: parameter for parameter in endpoint.parameters}
        unknown_arguments = sorted(set(call.arguments) - set(declared_parameters))
        if unknown_arguments:
            raise PlanValidationError(
                f"undeclared arguments for {call.tool}.{call.endpoint}: "
                + ", ".join(unknown_arguments)
            )

        actual_missing = sorted(
            parameter.name
            for parameter in endpoint.parameters
            if parameter.required and parameter.name not in call.arguments
        )
        if actual_missing:
            raise PlanValidationError(
                f"missing required arguments for {call.tool}.{call.endpoint}: "
                + ", ".join(actual_missing)
            )

        validate_json_schema_value(
            call.arguments,
            effective_input_schema(endpoint),
            context=f"arguments for {call.tool}.{call.endpoint}",
        )

        self.policy.validate(tool, endpoint, call)

        if self.authorization_policy is not None:
            principal = _current_principal_context()
            if principal is None:
                raise PolicyViolationError(
                    "authorization denied for requested capability"
                )
            self.authorization_policy.validate(
                principal,
                tool,
                endpoint,
                call,
            )

        declared_fields = {field.name for field in endpoint.output_fields}
        unknown_fields = sorted(set(call.fields) - declared_fields)
        if unknown_fields:
            raise PlanValidationError(
                f"undeclared output fields for {call.tool}.{call.endpoint}: "
                + ", ".join(unknown_fields)
            )
        if len(call.fields) != len(set(call.fields)):
            raise PlanValidationError(
                f"duplicate output fields for {call.tool}.{call.endpoint}"
            )
        if endpoint.output_fields and not call.fields:
            raise PlanValidationError(
                f"explicit output projection required for {call.tool}.{call.endpoint}"
            )

        actual_available = available_evidence(
            tool,
            endpoint,
            call.fields,
        )
        evidence_overclaims: list[str] = []
        if call.evidence.provenance and not actual_available.provenance:
            evidence_overclaims.append("provenance")
        if call.evidence.license and not actual_available.license:
            evidence_overclaims.append("license")
        if call.evidence.units and not actual_available.units:
            evidence_overclaims.append("units")
        if (
            call.evidence.source_type is not None
            and call.evidence.source_type != actual_available.source_type
        ):
            evidence_overclaims.append(
                f"source_type={call.evidence.source_type}"
            )
        if evidence_overclaims:
            raise PlanValidationError(
                f"call evidence overclaims current contract for "
                f"{call.tool}.{call.endpoint}: "
                + ", ".join(evidence_overclaims)
            )

        global_ok, _, global_missing = global_evidence_status(
            tool,
            endpoint,
            call.fields,
            call.required_evidence,
        )
        if not global_ok:
            raise PlanValidationError(
                f"required evidence unavailable for {call.tool}.{call.endpoint}: "
                + ", ".join(global_missing)
            )

        if call.required_evidence.source_type is not None:
            conflicting_field_source_types = sorted(
                field_name
                for field_name, requirement in call.field_evidence.items()
                if (
                    requirement.source_type is not None
                    and requirement.source_type
                    != call.required_evidence.source_type
                )
            )
            if conflicting_field_source_types:
                raise PlanValidationError(
                    "field evidence source_type conflicts with global required evidence "
                    f"for {call.tool}.{call.endpoint}: "
                    + ", ".join(conflicting_field_source_types)
                )

        field_ok, _, field_missing = field_evidence_status(
            tool,
            endpoint,
            call.fields,
            call.field_evidence,
        )
        if not field_ok:
            raise PlanValidationError(
                f"field evidence requirements unavailable for "
                f"{call.tool}.{call.endpoint}: "
                + ", ".join(field_missing)
            )

        return tool, endpoint

    def validate_call(self, call: ToolCall) -> None:
        self._validated_call_contract(call)

    async def _approve(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
        tracker: ExecutionBudgetTracker,
    ) -> bool:
        if not self.policy.requires_approval(endpoint, tool=tool, call=call):
            return False
        if self.approval_callback is None:
            raise ApprovalDeniedError(
                f"operation {call.tool}.{call.endpoint} requires trusted local approval"
            )
        try:
            decision = self.approval_callback(
                tool.model_copy(deep=True),
                endpoint.model_copy(deep=True),
                call.model_copy(deep=True),
            )
            if inspect.isawaitable(decision):
                decision = await tracker.wait_awaitable(
                    decision,
                    stage="approval callback",
                )
            else:
                tracker._check_elapsed(stage="approval callback")
        except (ApprovalDeniedError, ExecutionBudgetExceededError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise ApprovalDeniedError(
                f"approval callback failed closed for {call.tool}.{call.endpoint}"
            ) from exc
        if decision is not True:
            raise ApprovalDeniedError(
                f"operation {call.tool}.{call.endpoint} was not approved"
            )
        return True

    def _binding_for_validated_contract(
        self,
        tool_key: str,
        tool_fingerprint: str,
    ) -> tuple[BoundEndpointInvoker, bool]:
        """Return one coherent binding snapshot for an already-validated contract."""

        binding = self._binding_snapshot(tool_key)
        if binding.invoker is None:
            raise ExecutionError(f"no invoker bound for tool {tool_key!r}")
        if binding.fingerprint != tool_fingerprint:
            raise BindingDriftError(
                f"invoker binding is stale for tool {tool_key!r}; rebind before execution"
            )
        return binding.invoker, binding.offload_sync

    def _execution_state(
        self,
        call: ToolCall,
    ) -> tuple[ToolSpec, EndpointSpec, BoundEndpointInvoker, bool]:
        tool, endpoint = self._validated_call_contract(call)
        invoker, offload_sync = self._binding_for_validated_contract(
            call.tool,
            tool.fingerprint,
        )
        return tool, endpoint, invoker, offload_sync

    async def _run_before_hooks(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
        tracker: ExecutionBudgetTracker,
    ) -> bool:
        ran = False
        for hook in self.hooks.before_call:
            ran = True
            try:
                outcome = hook(
                    tool.model_copy(deep=True),
                    endpoint.model_copy(deep=True),
                    call.model_copy(deep=True),
                )
                if inspect.isawaitable(outcome):
                    outcome = await tracker.wait_awaitable(
                        outcome,
                        stage="before execution hook",
                    )
                else:
                    tracker._check_elapsed(stage="before execution hook")
            except (ExecutionHookError, ExecutionBudgetExceededError):
                raise
            except Exception as exc:  # noqa: BLE001
                raise ExecutionHookError(
                    f"before execution hook failed for {call.tool}.{call.endpoint}"
                ) from exc
            if outcome is not None:
                raise ExecutionHookError(
                    "before execution hooks must return None"
                )
        return ran

    async def _run_after_hooks(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
        result: ToolResult,
        tracker: ExecutionBudgetTracker,
    ) -> None:
        for hook in self.hooks.after_call:
            try:
                outcome = hook(
                    tool.model_copy(deep=True),
                    endpoint.model_copy(deep=True),
                    call.model_copy(deep=True),
                    result.model_copy(deep=True),
                )
                if inspect.isawaitable(outcome):
                    outcome = await tracker.wait_awaitable(
                        outcome,
                        stage="after execution hook",
                    )
                else:
                    tracker._check_elapsed(stage="after execution hook")
            except asyncio.CancelledError as exc:
                raise PostInvocationHookError(
                    (
                        "after execution hook was cancelled after successful invocation "
                        f"for {call.tool}.{call.endpoint}"
                    ),
                    result=result.model_copy(deep=True),
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise PostInvocationHookError(
                    f"after execution hook failed after successful invocation "
                    f"for {call.tool}.{call.endpoint}",
                    result=result.model_copy(deep=True),
                ) from exc
            if outcome is not None:
                raise PostInvocationHookError(
                    "after execution hooks must return None after successful invocation",
                    result=result.model_copy(deep=True),
                )

    def _authorization_scope_for_attempt(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> DataScopeDecision | None:
        """Authorize one imminent invocation against one immutable policy snapshot."""

        policy = self.authorization_policy
        if policy is None:
            return None

        principal = _current_principal_context()
        if principal is None:
            raise PolicyViolationError(
                "authorization denied for requested capability"
            )

        decision = policy.evaluate(principal, tool, endpoint, call)
        if decision.effect != "allow":
            raise PolicyViolationError(
                "authorization denied for requested capability"
            )
        return policy.validate_data_scope(
            principal,
            tool,
            endpoint,
            call,
        )

    async def execute_call(
        self,
        call: ToolCall,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
        _tracker: ExecutionBudgetTracker | None = None,
    ) -> ToolResult:
        tracker = _tracker or ExecutionBudgetTracker(budget or ExecutionBudget())
        tool, endpoint, invoker, offload_sync = self._execution_state(call)

        approval_ran = await self._approve(tool, endpoint, call, tracker)

        # Trusted callbacks may mutate or await while schema/bindings change. Refresh only when
        # such a callback actually ran; otherwise keep the validated registry snapshot coherent.
        if approval_ran:
            tool, endpoint, invoker, offload_sync = self._execution_state(call)

        await tracker.before_call(call)

        before_hooks_ran = await self._run_before_hooks(tool, endpoint, call, tracker)
        if before_hooks_ran:
            tool, endpoint, invoker, offload_sync = self._execution_state(call)

        retry = retry or RetryPolicy()
        can_retry = endpoint.read_only is True or retry.retry_non_read_only
        max_attempts = retry.max_attempts if can_retry else 1
        delay = min(retry.initial_backoff_seconds, retry.max_backoff_seconds)

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            await tracker.before_attempt(call, tool)

            # Retry backoff, hooks, and other trusted awaits may outlive the policy snapshot
            # used for planning or the previous attempt. Preserve the already-validated
            # registry contract, but refresh the process-local binding as one coherent snapshot
            # and re-authorize immediately before each actual invoker boundary.
            invoker, offload_sync = self._binding_for_validated_contract(
                call.tool,
                tool.fingerprint,
            )
            data_scope = self._authorization_scope_for_attempt(
                tool,
                endpoint,
                call,
            )

            try:
                invoke_call = getattr(invoker, "invoke_call", None)
                call_aware = callable(invoke_call)
                with _data_scope_execution_context(data_scope):
                    sync_offloaded = False
                    if call_aware:
                        if offload_sync and not inspect.iscoroutinefunction(invoke_call):
                            value = asyncio.to_thread(invoke_call, call)
                            sync_offloaded = True
                        else:
                            value = invoke_call(call)
                    else:
                        endpoint_invoker = cast(EndpointInvoker, invoker)
                        if offload_sync and not inspect.iscoroutinefunction(endpoint_invoker):
                            value = asyncio.to_thread(
                                endpoint_invoker,
                                call.endpoint,
                                dict(call.arguments),
                            )
                            sync_offloaded = True
                        else:
                            value = endpoint_invoker(
                                call.endpoint,
                                dict(call.arguments),
                            )
                    if inspect.isawaitable(value):
                        if sync_offloaded and endpoint.read_only is not True:
                            value = await self._await_side_effecting_offloaded_sync(
                                value,
                                tracker=tracker,
                                call=call,
                            )
                        else:
                            value = await tracker.wait_awaitable(
                                value,
                                stage="invocation",
                            )
                tracker.after_attempt()

                server_projected = (
                    call_aware
                    and endpoint.server_projection is not None
                    and bool(call.fields)
                )
                validate_json_schema_value(
                    value,
                    (
                        projected_output_schema(endpoint, call.fields)
                        if server_projected
                        else effective_output_schema(endpoint)
                    ),
                    context=f"output from {call.tool}.{call.endpoint}",
                )
                if server_projected:
                    self._validate_selected_fields_present(
                        value,
                        call.fields,
                        endpoint,
                        context=f"output from {call.tool}.{call.endpoint}",
                    )
                self._validate_selected_field_schemas(
                    value,
                    call.fields,
                    endpoint,
                    context=f"output from {call.tool}.{call.endpoint}",
                )
                selected_field_specs = {
                    field.name: field
                    for field in endpoint.output_fields
                    if field.name in call.fields
                }
                has_explicit_paths = any(
                    field.path
                    or field.result_projection_path != field.projection_path
                    for field in selected_field_specs.values()
                )
                adapter_projected = (
                    call_aware
                    and bool(getattr(invoker, "projects_fields", False))
                    and not has_explicit_paths
                )
                projected = (
                    value
                    if adapter_projected
                    else self._project(value, call.fields, endpoint)
                )
                projected = self._normalize_projected_units(
                    projected,
                    call.fields,
                    endpoint,
                )
                result = ToolResult(
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=projected,
                    projected_fields=call.fields,
                    field_contracts=self._result_field_contracts(
                        call.fields,
                        endpoint,
                    ),
                )
                await self._run_after_hooks(tool, endpoint, call, result, tracker)
                tracker.after_attempt()
                self._mark_access_available_for_contract(
                    call.tool,
                    call.endpoint,
                    tool.fingerprint,
                )
                return result
            except (
                SchemaValidationError,
                ExecutionBudgetExceededError,
                ExecutionHookError,
                NonRetryableInvocationError,
            ):
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= max_attempts:
                    break
                if delay > 0:
                    await tracker.wait_backoff(delay)
                    delay = min(
                        retry.max_backoff_seconds,
                        delay * retry.backoff_multiplier,
                    )

        if isinstance(last_error, InvocationUnavailableError):
            self._mark_access_unavailable_for_contract(
                call.tool,
                call.endpoint,
                tool.fingerprint,
            )
            raise last_error
        raise ExecutionError(
            f"invocation failed for {call.tool}.{call.endpoint} after {max_attempts} attempt(s)"
        ) from last_error

    def validate_fallback_chain(
        self,
        call: ToolCall,
        alternatives: list[ToolCall] | tuple[ToolCall, ...],
    ) -> None:
        chain = [call, *alternatives]

        # Read-only eligibility is a structural invariant for every *current* fallback
        # contract. Optional alternatives that were removed or drifted since planning are already
        # non-executable and are pruned later; they must not block a still-valid primary.
        for index, candidate in enumerate(chain):
            try:
                tool = self.registry.get(candidate.tool)
                endpoint = tool.endpoint(candidate.endpoint)
            except KeyError as exc:
                if index == 0:
                    raise PlanValidationError(
                        f"unknown tool/endpoint: {candidate.tool}.{candidate.endpoint}"
                    ) from exc
                continue

            if index > 0 and (
                candidate.schema_fingerprint != endpoint.fingerprint
                or (
                    candidate.tool_fingerprint is not None
                    and candidate.tool_fingerprint != tool.fingerprint
                )
            ):
                continue

            if endpoint.read_only is not True:
                raise PlanValidationError(
                    "automatic fallback requires every current candidate to be explicitly "
                    f"read-only; got {candidate.tool}.{candidate.endpoint}"
                )

        # The primary call remains fail-closed for schema/policy drift. Optional alternatives are
        # validated/pruned individually by ordered_available_fallback_chain before execution.
        self._validated_call_contract(call)

    async def execute_call_with_fallback(
        self,
        call: ToolCall,
        alternatives: list[ToolCall] | tuple[ToolCall, ...],
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
        _tracker: ExecutionBudgetTracker | None = None,
    ) -> ToolResult:
        tracker = _tracker or ExecutionBudgetTracker(budget or ExecutionBudget())
        last_unavailable: InvocationUnavailableError | None = None

        # Validate the bounded chain before invoking anything. Mutating alternatives invalidate
        # the chain structurally. Optional read-only alternatives that are stale, unbound,
        # policy-denied, or in cooldown are pruned before the primary runs.
        chain = (
            self.ordered_available_fallback_chain(call, alternatives)
            if alternatives
            else [call]
        )

        for candidate in chain:
            try:
                return await self.execute_call(
                    candidate,
                    retry=retry,
                    budget=budget,
                    _tracker=tracker,
                )
            except InvocationUnavailableError as exc:
                last_unavailable = exc
                continue

        if last_unavailable is not None:
            raise last_unavailable
        raise ExecutionError("fallback chain contained no executable candidates")

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
    ) -> list[ToolResult]:
        return [
            result
            async for result in self.execute_iter(plan, retry=retry, budget=budget)
        ]

    def validate_parallel_read_only(self, plan: ExecutionPlan) -> None:
        """Fail before launching tasks unless every primary group has a trusted read-only route."""

        for index, call in enumerate(plan.calls):
            route = plan.fallback_route(index)
            if route is not None:
                # This performs structural read-only validation for the whole bounded chain,
                # keeps the primary schema/policy fail-closed, and requires at least one currently
                # bound + available candidate without letting optional unusable fallbacks block it.
                self.ordered_available_fallback_chain(
                    call,
                    route.alternatives,
                )
                continue

            try:
                endpoint = self.registry.endpoint(call.tool, call.endpoint)
            except KeyError as exc:
                raise PlanValidationError(
                    f"unknown tool/endpoint: {call.tool}.{call.endpoint}"
                ) from exc
            if endpoint.read_only is not True:
                raise PlanValidationError(
                    "parallel_read_only execution requires every call to be explicitly "
                    f"read-only; got {call.tool}.{call.endpoint}"
                )
            self._execution_state(call)

    async def execute_parallel_read_only(
        self,
        plan: ExecutionPlan,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
        max_concurrency: int = 8,
    ) -> list[ToolResult]:
        completed = [
            item
            async for item in self.execute_parallel_read_only_iter(
                plan,
                retry=retry,
                budget=budget,
                max_concurrency=max_concurrency,
            )
        ]
        completed.sort(key=lambda item: item[0])
        return [result for _, result in completed]

    async def execute_parallel_read_only_iter(
        self,
        plan: ExecutionPlan,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
        max_concurrency: int = 8,
    ) -> AsyncIterator[tuple[int, ToolResult]]:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        self.validate_parallel_read_only(plan)
        tracker = ExecutionBudgetTracker(budget or ExecutionBudget())
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_one(index: int, call: ToolCall) -> tuple[int, ToolResult]:
            async with semaphore:
                route = plan.fallback_route(index)
                result = await self.execute_call_with_fallback(
                    call,
                    route.alternatives if route is not None else [],
                    retry=retry,
                    budget=budget,
                    _tracker=tracker,
                )
                return index, result

        tasks = [
            asyncio.create_task(run_one(index, call))
            for index, call in enumerate(plan.calls)
        ]
        try:
            for completed in asyncio.as_completed(tasks):
                yield await completed
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_iter(
        self,
        plan: ExecutionPlan,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
    ) -> AsyncIterator[ToolResult]:
        tracker = ExecutionBudgetTracker(budget or ExecutionBudget())
        for index, call in enumerate(plan.calls):
            route = plan.fallback_route(index)
            yield await self.execute_call_with_fallback(
                call,
                route.alternatives if route is not None else [],
                retry=retry,
                budget=budget,
                _tracker=tracker,
            )

    @staticmethod
    def _extract_projection_path(
        value: Any,
        path: tuple[str, ...],
    ) -> Any:
        if not path:
            return deepcopy(value)

        part = path[0]
        rest = path[1:]
        if part == "*":
            if not isinstance(value, list):
                return _MISSING
            return [
                RegistryExecutor._extract_projection_path(item, rest)
                for item in value
            ]

        if not isinstance(value, dict) or part not in value:
            return _MISSING
        return RegistryExecutor._extract_projection_path(value[part], rest)

    @staticmethod
    def _flatten_projection_values(value: Any) -> list[Any]:
        if value is _MISSING:
            return []
        if isinstance(value, list):
            flattened: list[Any] = []
            for item in value:
                flattened.extend(RegistryExecutor._flatten_projection_values(item))
            return flattened
        return [value]

    @staticmethod
    def _insert_projection_value(
        target: Any,
        path: tuple[str, ...],
        value: Any,
        *,
        field_name: str,
        endpoint_name: str,
    ) -> None:
        if not path or value is _MISSING:
            return

        part = path[0]
        rest = path[1:]
        if part == "*":
            if not isinstance(target, list) or not isinstance(value, list):
                raise PlanValidationError(
                    "array-item projection shape mismatch for "
                    f"{field_name!r} in {endpoint_name!r}"
                )

            if target and len(target) != len(value):
                raise PlanValidationError(
                    "array-item projection length collision for "
                    f"{field_name!r} in {endpoint_name!r}"
                )
            if not target:
                target.extend([None] * len(value))

            for index, item in enumerate(value):
                if item is _MISSING:
                    if target[index] is None and rest:
                        target[index] = [] if rest[0] == "*" else {}
                    continue
                if not rest:
                    target[index] = deepcopy(item)
                    continue

                desired: Any = [] if rest[0] == "*" else {}
                current = target[index]
                if current is None:
                    current = desired
                    target[index] = current
                elif type(current) is not type(desired):
                    raise PlanValidationError(
                        "array-item projection result-path collision for "
                        f"{field_name!r} in {endpoint_name!r}"
                    )
                RegistryExecutor._insert_projection_value(
                    current,
                    rest,
                    item,
                    field_name=field_name,
                    endpoint_name=endpoint_name,
                )
            return

        if not isinstance(target, dict):
            raise PlanValidationError(
                "nested projection result-path collision for "
                f"{field_name!r} in {endpoint_name!r}"
            )

        if not rest:
            target[part] = deepcopy(value)
            return

        desired = [] if rest[0] == "*" else {}
        current = target.get(part)
        if current is None:
            current = desired
            target[part] = current
        elif type(current) is not type(desired):
            raise PlanValidationError(
                "nested projection result-path collision for "
                f"{field_name!r} in {endpoint_name!r}"
            )
        RegistryExecutor._insert_projection_value(
            current,
            rest,
            value,
            field_name=field_name,
            endpoint_name=endpoint_name,
        )

    @staticmethod
    def _transform_projection_path(
        value: Any,
        path: tuple[str, ...],
        transform,
    ) -> None:
        if not path:
            return

        part = path[0]
        rest = path[1:]
        if part == "*":
            if not isinstance(value, list):
                return
            if not rest:
                for index, item in enumerate(value):
                    value[index] = transform(item)
                return
            for item in value:
                RegistryExecutor._transform_projection_path(item, rest, transform)
            return

        if not isinstance(value, dict) or part not in value:
            return
        if not rest:
            value[part] = transform(value[part])
            return
        RegistryExecutor._transform_projection_path(value[part], rest, transform)

    @staticmethod
    def _validate_selected_fields_present(
        value: Any,
        fields: list[str],
        endpoint: EndpointSpec,
        *,
        context: str,
    ) -> None:
        if not fields:
            return

        if isinstance(value, dict):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            return

        field_map = {field.name: field for field in endpoint.output_fields}
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for field_name in fields:
                field = field_map[field_name]
                if "*" in field.projection_path:
                    extracted = RegistryExecutor._extract_projection_path(
                        item,
                        field.projection_path,
                    )
                    # Once the declared array itself is present, optional descendants may
                    # legitimately be absent from individual records. Record alignment is
                    # preserved by projection rather than treating those rows as an error.
                    if extracted is not _MISSING:
                        continue
                    missing = True
                else:
                    current: Any = item
                    missing = False
                    for part in field.projection_path:
                        if not isinstance(current, dict) or part not in current:
                            missing = True
                            break
                        current = current[part]
                if missing:
                    suffix = (
                        f" item {item_index}"
                        if isinstance(value, list)
                        else ""
                    )
                    raise SchemaValidationError(
                        f"{context}{suffix}: projected field {field_name!r} is missing"
                    )

    @staticmethod
    def _validate_selected_field_schemas(
        value: Any,
        fields: list[str],
        endpoint: EndpointSpec,
        *,
        context: str,
    ) -> None:
        if not fields:
            return
        if isinstance(value, dict):
            items = [value]
        elif isinstance(value, list):
            items = value
        else:
            return

        field_map = {field.name: field for field in endpoint.output_fields}
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for field_name in fields:
                field = field_map.get(field_name)
                if field is None or not field.json_schema:
                    continue

                suffix = (
                    f" item {item_index}"
                    if isinstance(value, list)
                    else ""
                )
                if "*" in field.projection_path:
                    extracted = RegistryExecutor._extract_projection_path(
                        item,
                        field.projection_path,
                    )
                    for child_index, current in enumerate(
                        RegistryExecutor._flatten_projection_values(extracted)
                    ):
                        validate_json_schema_value(
                            current,
                            field.json_schema,
                            context=(
                                f"{context}{suffix} field {field_name!r} "
                                f"array item {child_index}"
                            ),
                        )
                    continue

                current: Any = item
                missing = False
                for part in field.projection_path:
                    if not isinstance(current, dict) or part not in current:
                        missing = True
                        break
                    current = current[part]
                if missing:
                    continue

                validate_json_schema_value(
                    current,
                    field.json_schema,
                    context=f"{context}{suffix} field {field_name!r}",
                )

    @staticmethod
    def _normalize_projected_units(
        value: Any,
        fields: list[str],
        endpoint: EndpointSpec,
    ) -> Any:
        if not fields:
            return value
        if isinstance(value, list):
            return [
                RegistryExecutor._normalize_projected_units(item, fields, endpoint)
                if isinstance(item, dict)
                else deepcopy(item)
                for item in value
            ]
        if not isinstance(value, dict):
            return value

        normalized = deepcopy(value)
        field_map = {field.name: field for field in endpoint.output_fields}
        for field_name in fields:
            field = field_map.get(field_name)
            if field is None or field.unit_normalization is None:
                continue

            path = field.result_projection_path
            spec = field.unit_normalization

            def convert_numeric(
                item: Any,
                *,
                _spec=spec,
                _field_name=field_name,
            ) -> Any:
                if item is None:
                    return None
                if isinstance(item, list):
                    return [convert_numeric(child) for child in item]
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    raise SchemaValidationError(
                        f"projected field {_field_name!r} requires numeric values "
                        "for unit normalization"
                    )
                try:
                    converted = item * _spec.scale + _spec.offset
                except OverflowError as exc:
                    raise SchemaValidationError(
                        f"projected field {_field_name!r} overflowed during unit normalization"
                    ) from exc
                if isinstance(converted, float) and not math.isfinite(converted):
                    raise SchemaValidationError(
                        f"projected field {_field_name!r} produced a non-finite normalized value"
                    )
                return converted

            if "*" in path:
                RegistryExecutor._transform_projection_path(
                    normalized,
                    path,
                    convert_numeric,
                )
                continue

            current: Any = normalized
            missing = False
            for part in path[:-1]:
                if not isinstance(current, dict) or part not in current:
                    missing = True
                    break
                current = current[part]
            if missing or not isinstance(current, dict) or path[-1] not in current:
                continue
            current[path[-1]] = convert_numeric(current[path[-1]])

        return normalized

    @staticmethod
    def _minimal_type_schema(schema: dict[str, Any]) -> dict[str, Any]:
        declared_types = sorted(json_schema_types(schema))
        result: dict[str, Any] = {}
        if declared_types:
            result["type"] = (
                declared_types[0]
                if len(declared_types) == 1
                else declared_types
            )
        if "array" in declared_types and isinstance(schema.get("items"), dict):
            item_schema = RegistryExecutor._minimal_type_schema(schema["items"])
            if item_schema:
                result["items"] = item_schema
        return result

    @staticmethod
    def _result_field_contracts(
        fields: list[str],
        endpoint: EndpointSpec,
    ) -> dict[str, ResultFieldContract]:
        field_map = {field.name: field for field in endpoint.output_fields}
        contracts: dict[str, ResultFieldContract] = {}
        for field_name in fields:
            field = field_map.get(field_name)
            if field is None:
                continue
            canonical_schema = canonical_field_value_schema(
                endpoint,
                field_name,
            )
            output_schema = RegistryExecutor._minimal_type_schema(canonical_schema)

            contracts[field_name] = ResultFieldContract(
                semantic_id=field.semantic_id,
                json_schema=output_schema,
                source_unit=field.unit,
                unit=(
                    field.unit_normalization.canonical_unit
                    if field.unit_normalization is not None
                    else field.unit
                ),
                dimension=(
                    field.unit_normalization.dimension
                    if field.unit_normalization is not None
                    else None
                ),
                qualifiers=dict(field.qualifiers),
            )
        return contracts

    @staticmethod
    def _project(value: Any, fields: list[str], endpoint: EndpointSpec) -> Any:
        if not fields:
            return value
        if isinstance(value, list):
            return [
                RegistryExecutor._project(item, fields, endpoint)
                if isinstance(item, dict)
                else deepcopy(item)
                for item in value
            ]
        if not isinstance(value, dict):
            return value

        field_map = {field.name: field for field in endpoint.output_fields}
        projected: dict[str, Any] = {}

        for field_name in fields:
            field = field_map[field_name]
            if "*" in field.projection_path:
                extracted = RegistryExecutor._extract_projection_path(
                    value,
                    field.projection_path,
                )
                RegistryExecutor._insert_projection_value(
                    projected,
                    field.result_projection_path,
                    extracted,
                    field_name=field_name,
                    endpoint_name=endpoint.name,
                )
                continue

            current: Any = value
            missing = False
            for part in field.projection_path:
                if not isinstance(current, dict) or part not in current:
                    missing = True
                    break
                current = current[part]
            if missing:
                continue

            target = projected
            result_path = field.result_projection_path
            for part in result_path[:-1]:
                child = target.get(part)
                if child is None:
                    child = {}
                    target[part] = child
                if not isinstance(child, dict):
                    raise PlanValidationError(
                        "nested projection result-path collision for "
                        f"{field_name!r} in {endpoint.name!r}"
                    )
                target = child
            target[result_path[-1]] = deepcopy(current)

        return projected

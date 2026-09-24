from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import AsyncIterator, Awaitable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from .errors import (
    ApprovalDeniedError,
    BindingDriftError,
    ExecutionBudgetExceededError,
    ExecutionError,
    ExecutionHookError,
    NonRetryableInvocationError,
    PlanValidationError,
    SchemaDriftError,
    SchemaValidationError,
)
from .hooks import ExecutionHooks
from .models import EndpointSpec, ExecutionPlan, ToolCall, ToolResult, ToolSpec
from .policy import ApprovalCallback, ExecutionPolicy, is_remote_tool
from .registry import ToolRegistry
from .runs import ExecutionBudget, RetryPolicy
from .validation import (
    effective_input_schema,
    effective_output_schema,
    validate_json_schema_value,
)


class EndpointInvoker(Protocol):
    def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]: ...


class CallAwareEndpointInvoker(Protocol):
    def invoke_call(self, call: ToolCall) -> Any | Awaitable[Any]: ...


@dataclass
class ExecutionBudgetTracker:
    budget: ExecutionBudget
    started: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    attempts: int = 0
    remote_attempts: int = 0
    cost_units: float = 0.0
    per_tool_calls: dict[str, int] = field(default_factory=dict)

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

    def before_call(self, call: ToolCall) -> None:
        self._check_elapsed()
        next_total = self.tool_calls + 1
        if self.budget.max_tool_calls is not None and next_total > self.budget.max_tool_calls:
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

    def before_attempt(self, call: ToolCall, tool: ToolSpec) -> None:
        self._check_elapsed()
        next_attempts = self.attempts + 1
        if self.budget.max_attempts is not None and next_attempts > self.budget.max_attempts:
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
        approval_callback: ApprovalCallback | None = None,
        hooks: ExecutionHooks | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self.approval_callback = approval_callback
        self.hooks = hooks or ExecutionHooks()
        self._invokers: dict[str, EndpointInvoker] = {}
        self._binding_fingerprints: dict[str, str] = {}

    def bind(self, tool_key: str, invoker: EndpointInvoker) -> None:
        tool = self.registry.get(tool_key)
        self._invokers[tool_key] = invoker
        self._binding_fingerprints[tool_key] = tool.fingerprint

    def unbind(self, tool_key: str) -> None:
        self._invokers.pop(tool_key, None)
        self._binding_fingerprints.pop(tool_key, None)

    def bound_keys(self) -> tuple[str, ...]:
        """Return live trusted-invoker keys without exposing invoker objects."""
        return tuple(sorted(self._invokers))

    def validate_call(self, call: ToolCall) -> None:
        try:
            tool = self.registry.get(call.tool)
            endpoint = tool.endpoint(call.endpoint)
        except KeyError as exc:
            message = f"unknown tool/endpoint: {call.tool}.{call.endpoint}"
            raise PlanValidationError(message) from exc

        if call.tool_fingerprint is None and (
            tool.remote or bool(endpoint.execution_metadata)
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

    async def _approve(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
        tracker: ExecutionBudgetTracker,
    ) -> None:
        if not self.policy.requires_approval(endpoint, tool=tool, call=call):
            return
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

    def _execution_state(
        self,
        call: ToolCall,
    ) -> tuple[ToolSpec, EndpointSpec, EndpointInvoker]:
        self.validate_call(call)
        endpoint = self.registry.endpoint(call.tool, call.endpoint)
        tool = self.registry.get(call.tool)
        invoker = self._invokers.get(call.tool)
        if invoker is None:
            raise ExecutionError(f"no invoker bound for tool {call.tool!r}")

        bound_fingerprint = self._binding_fingerprints.get(call.tool)
        if bound_fingerprint != tool.fingerprint:
            raise BindingDriftError(
                f"invoker binding is stale for tool {call.tool!r}; rebind before execution"
            )
        return tool, endpoint, invoker

    async def _run_before_hooks(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
        tracker: ExecutionBudgetTracker,
    ) -> None:
        for hook in self.hooks.before_call:
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
            except (ExecutionHookError, ExecutionBudgetExceededError):
                raise
            except Exception as exc:  # noqa: BLE001
                raise ExecutionHookError(
                    f"after execution hook failed for {call.tool}.{call.endpoint}"
                ) from exc
            if outcome is not None:
                raise ExecutionHookError(
                    "after execution hooks must return None"
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
        tool, endpoint, invoker = self._execution_state(call)

        await self._approve(tool, endpoint, call, tracker)

        # Trusted callbacks may await while schema or bindings change. Refresh all executable state
        # after approval and again after before-hooks so stale local references cannot execute.
        tool, endpoint, invoker = self._execution_state(call)

        tracker.before_call(call)

        await self._run_before_hooks(tool, endpoint, call, tracker)
        tool, endpoint, invoker = self._execution_state(call)

        retry = retry or RetryPolicy()
        can_retry = endpoint.read_only is True or retry.retry_non_read_only
        max_attempts = retry.max_attempts if can_retry else 1
        delay = min(retry.initial_backoff_seconds, retry.max_backoff_seconds)

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            tracker.before_attempt(call, tool)
            try:
                invoke_call = getattr(invoker, "invoke_call", None)
                call_aware = callable(invoke_call)
                if call_aware:
                    value = invoke_call(call)
                else:
                    value = invoker(call.endpoint, dict(call.arguments))
                if inspect.isawaitable(value):
                    value = await tracker.wait_awaitable(
                        value,
                        stage="invocation",
                    )
                tracker.after_attempt()

                validate_json_schema_value(
                    value,
                    effective_output_schema(endpoint),
                    context=f"output from {call.tool}.{call.endpoint}",
                )
                selected_field_specs = {
                    field.name: field
                    for field in endpoint.output_fields
                    if field.name in call.fields
                }
                has_explicit_paths = any(
                    field.path for field in selected_field_specs.values()
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
                result = ToolResult(
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=projected,
                    projected_fields=call.fields,
                )
                await self._run_after_hooks(tool, endpoint, call, result, tracker)
                tracker.after_attempt()
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

        raise ExecutionError(
            f"invocation failed for {call.tool}.{call.endpoint} after {max_attempts} attempt(s)"
        ) from last_error

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
        """Fail before launching tasks unless every call is currently trusted read-only."""

        for call in plan.calls:
            tool, endpoint, _ = self._execution_state(call)
            if endpoint.read_only is not True:
                raise PlanValidationError(
                    "parallel_read_only execution requires every call to be explicitly "
                    f"read-only; got {call.tool}.{call.endpoint}"
                )
            # Keep the local tool snapshot read so policy/binding validation happens for every
            # call before any parallel task is launched.
            del tool

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
                result = await self.execute_call(
                    call,
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
        for call in plan.calls:
            yield await self.execute_call(
                call,
                retry=retry,
                budget=budget,
                _tracker=tracker,
            )

    @staticmethod
    def _project(value: Any, fields: list[str], endpoint: EndpointSpec) -> Any:
        if not fields or not isinstance(value, dict):
            return value

        field_map = {field.name: field for field in endpoint.output_fields}
        projected: dict[str, Any] = {}

        for field_name in fields:
            field = field_map[field_name]
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
            path = field.projection_path
            for part in path[:-1]:
                child = target.get(part)
                if child is None:
                    child = {}
                    target[part] = child
                if not isinstance(child, dict):
                    raise PlanValidationError(
                        "nested projection path collision for "
                        f"{field_name!r} in {endpoint.name!r}"
                    )
                target = child
            target[path[-1]] = deepcopy(current)

        return projected

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .errors import (
    ApprovalDeniedError,
    BindingDriftError,
    ExecutionBudgetExceededError,
    ExecutionError,
    PlanValidationError,
    SchemaDriftError,
    SchemaValidationError,
)
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

    def _check_elapsed(self) -> None:
        limit = self.budget.max_elapsed_seconds
        if limit is not None and time.monotonic() - self.started >= limit:
            raise ExecutionBudgetExceededError(
                f"execution exceeded max_elapsed_seconds={limit}"
            )

    def remaining_seconds(self) -> float | None:
        limit = self.budget.max_elapsed_seconds
        if limit is None:
            return None
        remaining = limit - (time.monotonic() - self.started)
        if remaining <= 0:
            self._check_elapsed()
        return max(remaining, 0.0)

    def after_attempt(self) -> None:
        self._check_elapsed()

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
    ) -> None:
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self.approval_callback = approval_callback
        self._invokers: dict[str, EndpointInvoker] = {}
        self._binding_fingerprints: dict[str, str] = {}

    def bind(self, tool_key: str, invoker: EndpointInvoker) -> None:
        tool = self.registry.get(tool_key)
        self._invokers[tool_key] = invoker
        self._binding_fingerprints[tool_key] = tool.fingerprint

    def unbind(self, tool_key: str) -> None:
        self._invokers.pop(tool_key, None)
        self._binding_fingerprints.pop(tool_key, None)

    def validate_call(self, call: ToolCall) -> None:
        try:
            endpoint = self.registry.endpoint(call.tool, call.endpoint)
        except KeyError as exc:
            message = f"unknown tool/endpoint: {call.tool}.{call.endpoint}"
            raise PlanValidationError(message) from exc

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

        tool = self.registry.get(call.tool)
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
    ) -> None:
        if not self.policy.requires_approval(endpoint):
            return
        if self.approval_callback is None:
            raise ApprovalDeniedError(
                f"operation {call.tool}.{call.endpoint} requires trusted local approval"
            )
        try:
            decision = self.approval_callback(tool, endpoint, call)
            if inspect.isawaitable(decision):
                decision = await decision
        except ApprovalDeniedError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ApprovalDeniedError(
                f"approval callback failed closed for {call.tool}.{call.endpoint}"
            ) from exc
        if decision is not True:
            raise ApprovalDeniedError(
                f"operation {call.tool}.{call.endpoint} was not approved"
            )

    async def execute_call(
        self,
        call: ToolCall,
        *,
        retry: RetryPolicy | None = None,
        budget: ExecutionBudget | None = None,
        _tracker: ExecutionBudgetTracker | None = None,
    ) -> ToolResult:
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

        await self._approve(tool, endpoint, call)

        tracker = _tracker or ExecutionBudgetTracker(budget or ExecutionBudget())
        tracker.before_call(call)

        retry = retry or RetryPolicy()
        can_retry = endpoint.read_only is True or retry.retry_non_read_only
        max_attempts = retry.max_attempts if can_retry else 1
        delay = retry.initial_backoff_seconds

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
                    remaining = tracker.remaining_seconds()
                    try:
                        value = (
                            await asyncio.wait_for(value, timeout=remaining)
                            if remaining is not None
                            else await value
                        )
                    except TimeoutError as exc:
                        raise ExecutionBudgetExceededError(
                            "execution exceeded max_elapsed_seconds during invocation"
                        ) from exc
                tracker.after_attempt()

                validate_json_schema_value(
                    value,
                    effective_output_schema(endpoint),
                    context=f"output from {call.tool}.{call.endpoint}",
                )
                adapter_projected = call_aware and bool(
                    getattr(invoker, "projects_fields", False)
                )
                projected = value if adapter_projected else self._project(value, call.fields)
                return ToolResult(
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=projected,
                    projected_fields=call.fields,
                )
            except (SchemaValidationError, ExecutionBudgetExceededError):
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= max_attempts:
                    break
                if delay > 0:
                    await asyncio.sleep(delay)
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
    def _project(value: Any, fields: list[str]) -> Any:
        if not fields or not isinstance(value, dict):
            return value
        return {name: value[name] for name in fields if name in value}

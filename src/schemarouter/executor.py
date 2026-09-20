from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable
from typing import Any, Protocol

from .errors import (
    BindingDriftError,
    ExecutionError,
    PlanValidationError,
    SchemaDriftError,
    SchemaValidationError,
)
from .models import ExecutionPlan, ToolCall, ToolResult
from .policy import ExecutionPolicy
from .registry import InMemoryRegistry
from .runs import RetryPolicy
from .validation import (
    effective_input_schema,
    effective_output_schema,
    validate_json_schema_value,
)


class EndpointInvoker(Protocol):
    def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]: ...


class RegistryExecutor:
    """Executes validated plans using caller-supplied trusted invokers."""

    def __init__(
        self,
        registry: InMemoryRegistry,
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self._invokers: dict[str, EndpointInvoker] = {}
        self._binding_fingerprints: dict[str, str] = {}

    def bind(self, tool_key: str, invoker: EndpointInvoker) -> None:
        tool = self.registry.get(tool_key)  # fail early for unknown tool
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

    async def execute_call(
        self,
        call: ToolCall,
        *,
        retry: RetryPolicy | None = None,
    ) -> ToolResult:
        self.validate_call(call)
        endpoint = self.registry.endpoint(call.tool, call.endpoint)
        invoker = self._invokers.get(call.tool)
        if invoker is None:
            raise ExecutionError(f"no invoker bound for tool {call.tool!r}")

        current_tool = self.registry.get(call.tool)
        bound_fingerprint = self._binding_fingerprints.get(call.tool)
        if bound_fingerprint != current_tool.fingerprint:
            raise BindingDriftError(
                f"invoker binding is stale for tool {call.tool!r}; rebind before execution"
            )

        retry = retry or RetryPolicy()
        can_retry = endpoint.read_only is True or retry.retry_non_read_only
        max_attempts = retry.max_attempts if can_retry else 1
        delay = retry.initial_backoff_seconds

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                value = invoker(call.endpoint, dict(call.arguments))
                if inspect.isawaitable(value):
                    value = await value

                validate_json_schema_value(
                    value,
                    effective_output_schema(endpoint),
                    context=f"output from {call.tool}.{call.endpoint}",
                )
                projected = self._project(value, call.fields)
                return ToolResult(
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=projected,
                    projected_fields=call.fields,
                )
            except SchemaValidationError as exc:
                last_error = exc
                if attempt >= max_attempts:
                    raise
                if delay > 0:
                    await asyncio.sleep(delay)
                    delay = min(
                        retry.max_backoff_seconds,
                        delay * retry.backoff_multiplier,
                    )
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
    ) -> list[ToolResult]:
        return [
            result
            async for result in self.execute_iter(plan, retry=retry)
        ]

    async def execute_iter(
        self,
        plan: ExecutionPlan,
        *,
        retry: RetryPolicy | None = None,
    ) -> AsyncIterator[ToolResult]:
        for call in plan.calls:
            yield await self.execute_call(call, retry=retry)

    @staticmethod
    def _project(value: Any, fields: list[str]) -> Any:
        if not fields or not isinstance(value, dict):
            return value
        return {name: value[name] for name in fields if name in value}

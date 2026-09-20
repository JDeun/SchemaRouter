from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any, Protocol

from .errors import ExecutionError, PlanValidationError, SchemaDriftError
from .models import ExecutionPlan, ToolCall, ToolResult
from .registry import InMemoryRegistry


class EndpointInvoker(Protocol):
    def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]: ...


class RegistryExecutor:
    """Executes validated plans using caller-supplied trusted invokers."""

    def __init__(self, registry: InMemoryRegistry) -> None:
        self.registry = registry
        self._invokers: dict[str, EndpointInvoker] = {}

    def bind(self, tool_key: str, invoker: EndpointInvoker) -> None:
        self.registry.get(tool_key)  # fail early for unknown tool
        self._invokers[tool_key] = invoker

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

    async def execute(self, plan: ExecutionPlan) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in plan.calls:
            self.validate_call(call)
            invoker = self._invokers.get(call.tool)
            if invoker is None:
                raise ExecutionError(f"no invoker bound for tool {call.tool!r}")
            try:
                value = invoker(call.endpoint, dict(call.arguments))
                if inspect.isawaitable(value):
                    value = await value
            except Exception as exc:  # noqa: BLE001
                raise ExecutionError(f"invocation failed for {call.tool}.{call.endpoint}") from exc

            projected = self._project(value, call.fields)
            results.append(
                ToolResult(
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=projected,
                    projected_fields=call.fields,
                )
            )
        return results

    @staticmethod
    def _project(value: Any, fields: list[str]) -> Any:
        if not fields or not isinstance(value, dict):
            return value
        return {name: value[name] for name in fields if name in value}

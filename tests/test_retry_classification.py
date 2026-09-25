import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionError,
    FieldSpec,
    InMemoryRegistry,
    NonRetryableInvocationError,
    RegistryExecutor,
    RetryPolicy,
    ToolCall,
    ToolSpec,
)
from schemarouter.adapters import OpenAPIRemoteInvoker
from schemarouter.adapters.optimade import OPTIMADERemoteInvoker


def _executor_for(
    tool: ToolSpec,
    invoker,
    *,
    fields: list[str] | None = None,
) -> tuple[RegistryExecutor, ToolCall]:
    registry = InMemoryRegistry()
    registry.register(tool)
    endpoint = tool.endpoints[0]
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=list(fields or []),
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    executor = RegistryExecutor(registry)
    executor.bind(tool.key, invoker)
    return executor, call


@pytest.mark.asyncio
async def test_explicit_non_retryable_invocation_error_stops_custom_retry_loop() -> None:
    tool = ToolSpec(
        name="custom",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    attempts = 0

    async def invoke(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        attempts += 1
        raise NonRetryableInvocationError("deterministic failure")

    executor, call = _executor_for(tool, invoke)

    with pytest.raises(NonRetryableInvocationError, match="deterministic failure"):
        await executor.execute_call(call, retry=RetryPolicy(max_attempts=3))

    assert attempts == 1


@pytest.mark.asyncio
async def test_generic_invocation_errors_preserve_existing_retry_behavior() -> None:
    tool = ToolSpec(
        name="custom",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    attempts = 0

    async def invoke(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("possibly transient")

    executor, call = _executor_for(tool, invoke)

    with pytest.raises(ExecutionError, match="after 3 attempt"):
        await executor.execute_call(call, retry=RetryPolicy(max_attempts=3))

    assert attempts == 3


@pytest.mark.asyncio
async def test_openapi_non_transient_http_status_fails_without_retry() -> None:
    tool = ToolSpec(
        name="api",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/items/1",
                read_only=True,
            )
        ],
        metadata={"adapter": "openapi", "remote": True},
    )
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"detail": "missing"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            http_client=client,
        )
        executor, call = _executor_for(tool, invoker)

        with pytest.raises(NonRetryableInvocationError, match="404"):
            await executor.execute_call(call, retry=RetryPolicy(max_attempts=3))

    assert attempts == 1


@pytest.mark.asyncio
async def test_openapi_transient_http_status_can_retry_and_recover() -> None:
    tool = ToolSpec(
        name="api",
        endpoints=[
            EndpointSpec(
                name="read",
                method="GET",
                path="/health",
                read_only=True,
            )
        ],
        metadata={"adapter": "openapi", "remote": True},
    )
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"detail": "busy"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OpenAPIRemoteInvoker(
            tool,
            "https://api.example.com",
            http_client=client,
        )
        executor, call = _executor_for(tool, invoker)
        result = await executor.execute_call(call, retry=RetryPolicy(max_attempts=2))

    assert attempts == 2
    assert result.data == {"ok": True}


@pytest.mark.asyncio
async def test_optimade_non_transient_http_status_fails_without_retry() -> None:
    fields = [
        FieldSpec(name="id", identifier=True),
        FieldSpec(name="type"),
    ]
    tool = ToolSpec(
        name="materials",
        endpoints=[
            EndpointSpec(
                name="search_structures",
                output_fields=fields,
                read_only=True,
                metadata={"entry_type": "structures", "mode": "search"},
            )
        ],
        metadata={"adapter": "optimade", "remote": True},
    )
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"errors": []}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OPTIMADERemoteInvoker(
            tool,
            "https://materials.example/v1",
            http_client=client,
        )
        executor, call = _executor_for(tool, invoker, fields=["id", "type"])

        with pytest.raises(NonRetryableInvocationError, match="404"):
            await executor.execute_call(call, retry=RetryPolicy(max_attempts=3))

    assert attempts == 1


@pytest.mark.asyncio
async def test_optimade_invalid_success_shape_fails_without_retry() -> None:
    fields = [
        FieldSpec(name="id", identifier=True),
        FieldSpec(name="type"),
    ]
    tool = ToolSpec(
        name="materials",
        endpoints=[
            EndpointSpec(
                name="search_structures",
                output_fields=fields,
                read_only=True,
                metadata={"entry_type": "structures", "mode": "search"},
            )
        ],
        metadata={"adapter": "optimade", "remote": True},
    )
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"data": {}}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OPTIMADERemoteInvoker(
            tool,
            "https://materials.example/v1",
            http_client=client,
        )
        executor, call = _executor_for(tool, invoker, fields=["id", "type"])

        with pytest.raises(
            NonRetryableInvocationError,
            match="data list",
        ):
            await executor.execute_call(call, retry=RetryPolicy(max_attempts=3))

    assert attempts == 1

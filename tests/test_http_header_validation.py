from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from schemarouter._http_headers import validate_trusted_headers
from schemarouter.adapters.base import AdapterContext
from schemarouter.adapters.graphql import GraphQLRemoteInvoker
from schemarouter.adapters.odata import ODataRemoteInvoker
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker
from schemarouter.adapters.openrpc import OpenRPCRemoteInvoker
from schemarouter.adapters.optimade import OPTIMADERemoteInvoker
from schemarouter.models import EndpointSpec, ToolSpec


def _tool() -> ToolSpec:
    return ToolSpec(name="header-fixture", endpoints=[EndpointSpec(name="noop")])


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "example.invalid"},
        {"Content-Length": "12"},
        {"Connection": "keep-alive"},
        {"Transfer-Encoding": "chunked"},
        {"X-Test": "bad\r\nvalue"},
        {"X-Test": "bad\x00value"},
        {"X-Test": "bad\tvalue"},
        {"Bad Header": "value"},
        {"X-Tenant": "a", "x-tenant": "b"},
    ],
)
def test_shared_trusted_header_validator_rejects_unsafe_input(
    headers: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        validate_trusted_headers(headers)


def test_shared_trusted_header_validator_keeps_host_owned_auth_headers() -> None:
    headers = {
        "Authorization": "Bearer runtime-value",
        "X-API-Key": "runtime-key",
        "Cookie": "session=trusted",
        "X-Tenant": "acme",
    }

    assert validate_trusted_headers(headers) == headers


def test_adapter_context_validates_discovery_and_runtime_headers() -> None:
    with pytest.raises(ValueError):
        AdapterContext(
            url="https://example.test/schema",
            schema_headers={"Host": "example.invalid"},
        )
    with pytest.raises(ValueError):
        AdapterContext(
            url="https://example.test/schema",
            trusted_headers={"X-Test": "bad\nvalue"},
        )


InvokerFactory = Callable[[ToolSpec, dict[str, str], Any], object]


@pytest.mark.parametrize(
    "factory",
    [
        lambda tool, headers, client: OpenAPIRemoteInvoker(
            tool,
            "https://example.test",
            trusted_headers=headers,
            http_client=client,
        ),
        lambda tool, headers, client: GraphQLRemoteInvoker(
            tool,
            "https://example.test/graphql",
            trusted_headers=headers,
            http_client=client,
        ),
        lambda tool, headers, client: OpenRPCRemoteInvoker(
            tool,
            "https://example.test/rpc",
            trusted_headers=headers,
            http_client=client,
        ),
        lambda tool, headers, client: ODataRemoteInvoker(
            tool,
            "https://example.test/odata",
            trusted_headers=headers,
            http_client=client,
        ),
        lambda tool, headers, client: OPTIMADERemoteInvoker(
            tool,
            "https://example.test/v1",
            trusted_headers=headers,
            http_client=client,
        ),
    ],
)
def test_remote_invokers_validate_headers_even_with_custom_clients(
    factory: InvokerFactory,
) -> None:
    custom_client = cast(Any, object())

    with pytest.raises(ValueError):
        factory(_tool(), {"Transfer-Encoding": "chunked"}, custom_client)

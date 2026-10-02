from schemarouter.adapters.graphql import _TRANSIENT_HTTP_STATUS_CODES as GRAPHQL_TRANSIENT
from schemarouter.adapters.odata import _TRANSIENT_HTTP_STATUS_CODES as ODATA_TRANSIENT
from schemarouter.adapters.openapi import _TRANSIENT_HTTP_STATUS_CODES as OPENAPI_TRANSIENT
from schemarouter.adapters.openrpc import _TRANSIENT_HTTP_STATUS_CODES as OPENRPC_TRANSIENT
from schemarouter.adapters.optimade import _TRANSIENT_HTTP_STATUS_CODES as OPTIMADE_TRANSIENT


def test_http_adapter_runtime_availability_classification_is_consistent() -> None:
    expected = {408, 425, 429, 500, 502, 503, 504}
    assert OPENAPI_TRANSIENT == expected
    assert OPTIMADE_TRANSIENT == expected
    assert GRAPHQL_TRANSIENT == expected
    assert ODATA_TRANSIENT == expected
    assert OPENRPC_TRANSIENT == expected


def test_permanent_protocol_http_errors_are_not_fallback_availability_signals() -> None:
    for statuses in (
        OPENAPI_TRANSIENT,
        OPTIMADE_TRANSIENT,
        GRAPHQL_TRANSIENT,
        ODATA_TRANSIENT,
        OPENRPC_TRANSIENT,
    ):
        assert 400 not in statuses
        assert 401 not in statuses
        assert 403 not in statuses
        assert 404 not in statuses
        assert 501 not in statuses
        assert 505 not in statuses

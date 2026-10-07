from __future__ import annotations

import inspect

from schemarouter import SchemaRouter
from schemarouter.runtime_defaults import RUNTIME_DEFAULTS, RuntimeDefaults


_POLICY_PARAMETERS = {
    "default_top_k": "vector_top_k",
    "default_limit": "query_limit",
    "default_max_hops": "graph_max_hops",
    "timeout": "timeout_seconds",
    "max_response_bytes": "http_response_max_bytes",
}


def test_runtime_defaults_preserve_existing_public_values() -> None:
    assert RUNTIME_DEFAULTS == RuntimeDefaults(
        vector_top_k=10,
        query_limit=100,
        graph_max_hops=1,
        timeout_seconds=20.0,
        http_response_max_bytes=10 * 1024 * 1024,
    )


def test_public_runtime_methods_source_common_defaults_from_policy() -> None:
    checked = {name: 0 for name in _POLICY_PARAMETERS}

    for method_name in dir(SchemaRouter):
        method = getattr(SchemaRouter, method_name)
        if not callable(method):
            continue
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            continue

        for parameter_name, default_name in _POLICY_PARAMETERS.items():
            parameter = signature.parameters.get(parameter_name)
            if parameter is None:
                continue
            assert parameter.default == getattr(RUNTIME_DEFAULTS, default_name), (
                method_name,
                parameter_name,
                parameter.default,
            )
            checked[parameter_name] += 1

    assert checked["default_top_k"] >= 10
    assert checked["default_limit"] >= 10
    assert checked["default_max_hops"] >= 5
    assert checked["timeout"] >= 5
    assert checked["max_response_bytes"] >= 1


def test_sync_async_registration_pairs_cannot_drift_on_shared_defaults() -> None:
    checked_pairs = 0
    for async_name in dir(SchemaRouter):
        if not async_name.startswith("aadd_"):
            continue
        sync_name = async_name[1:]
        if not hasattr(SchemaRouter, sync_name):
            continue

        async_signature = inspect.signature(getattr(SchemaRouter, async_name))
        sync_signature = inspect.signature(getattr(SchemaRouter, sync_name))
        common_policy_parameters = (
            set(async_signature.parameters)
            & set(sync_signature.parameters)
            & set(_POLICY_PARAMETERS)
        )
        if not common_policy_parameters:
            continue

        checked_pairs += 1
        for parameter_name in common_policy_parameters:
            assert (
                async_signature.parameters[parameter_name].default
                == sync_signature.parameters[parameter_name].default
            ), (async_name, sync_name, parameter_name)

    assert checked_pairs >= 8

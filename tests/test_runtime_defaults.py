import inspect
from collections.abc import Callable

import pytest

from schemarouter.runtime import SchemaRouter
from schemarouter.runtime_defaults import RUNTIME_DEFAULTS, RuntimeDefaults


def _defaults_for(parameter_name: str) -> dict[str, object]:
    defaults: dict[str, object] = {}
    for method_name, method in inspect.getmembers(SchemaRouter, inspect.isfunction):
        parameter = inspect.signature(method).parameters.get(parameter_name)
        if parameter is None or parameter.default is inspect.Parameter.empty:
            continue
        defaults[method_name] = parameter.default
    return defaults


@pytest.mark.parametrize(
    ("parameter_name", "expected"),
    [
        ("default_top_k", RUNTIME_DEFAULTS.vector_top_k),
        ("default_limit", RUNTIME_DEFAULTS.collection_limit),
        ("default_max_hops", RUNTIME_DEFAULTS.graph_max_hops),
        ("max_discovery_sources", RUNTIME_DEFAULTS.max_discovery_sources),
        ("max_fields_per_collection", RUNTIME_DEFAULTS.max_fields_per_collection),
        ("max_generated_bytes", RUNTIME_DEFAULTS.max_generated_bytes),
        ("max_response_bytes", RUNTIME_DEFAULTS.max_response_bytes),
        ("openapi_ref_max_depth", RUNTIME_DEFAULTS.openapi_ref_max_depth),
        ("openapi_ref_max_documents", RUNTIME_DEFAULTS.openapi_ref_max_documents),
        ("openapi_ref_max_bytes", RUNTIME_DEFAULTS.openapi_ref_max_bytes),
        ("max_document_chars", RUNTIME_DEFAULTS.documentation_max_chars),
    ],
)
def test_shared_runtime_parameter_defaults_use_policy(
    parameter_name: str,
    expected: object,
) -> None:
    defaults = _defaults_for(parameter_name)
    assert defaults, f"expected at least one runtime method with {parameter_name}"
    assert set(defaults.values()) == {expected}


@pytest.mark.parametrize("parameter_name", ["timeout", "timeout_seconds"])
def test_runtime_transport_timeout_defaults_do_not_drift(parameter_name: str) -> None:
    defaults = _defaults_for(parameter_name)
    assert defaults, f"expected at least one runtime method with {parameter_name}"
    assert set(defaults.values()) == {RUNTIME_DEFAULTS.transport_timeout_seconds}


def test_sync_async_registration_defaults_match() -> None:
    compared_pairs = 0
    for async_name, async_method in inspect.getmembers(
        SchemaRouter,
        inspect.isfunction,
    ):
        if not (async_name.startswith("aadd_") or async_name == "arefresh_schema"):
            continue
        sync_name = async_name[1:]
        sync_method = getattr(SchemaRouter, sync_name, None)
        if sync_method is None or not inspect.isfunction(sync_method):
            continue

        async_parameters = inspect.signature(async_method).parameters
        sync_parameters = inspect.signature(sync_method).parameters
        shared = set(async_parameters) & set(sync_parameters)
        for parameter_name in shared:
            async_default = async_parameters[parameter_name].default
            sync_default = sync_parameters[parameter_name].default
            if (
                async_default is inspect.Parameter.empty
                or sync_default is inspect.Parameter.empty
            ):
                continue
            assert sync_default == async_default, (
                f"{sync_name}.{parameter_name} default drifted from "
                f"{async_name}.{parameter_name}"
            )
        compared_pairs += 1

    assert compared_pairs >= 3


def test_runtime_defaults_preserve_existing_public_values() -> None:
    assert RUNTIME_DEFAULTS.vector_top_k == 10
    assert RUNTIME_DEFAULTS.collection_limit == 100
    assert RUNTIME_DEFAULTS.graph_max_hops == 1
    assert RUNTIME_DEFAULTS.max_discovery_sources == 128
    assert RUNTIME_DEFAULTS.max_fields_per_collection == 256
    assert RUNTIME_DEFAULTS.max_generated_bytes == 8 * 1024 * 1024
    assert RUNTIME_DEFAULTS.transport_timeout_seconds == 20.0
    assert RUNTIME_DEFAULTS.max_response_bytes == 10 * 1024 * 1024


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RuntimeDefaults(vector_top_k=0),
        lambda: RuntimeDefaults(collection_limit=-1),
        lambda: RuntimeDefaults(graph_max_hops=False),
        lambda: RuntimeDefaults(transport_timeout_seconds=0),
    ],
)
def test_runtime_defaults_reject_non_positive_values(
    factory: Callable[[], RuntimeDefaults],
) -> None:
    with pytest.raises(ValueError):
        factory()

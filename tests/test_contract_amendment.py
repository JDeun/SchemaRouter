"""Contracts for trusted local amendment of an imported capability (#509).

The local application is the execution authority, so it may declare and
annotate what a result *means*. It may not change what gets executed or how a
response is validated. These tests pin that split.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from schemarouter import (
    ContractAmendmentError,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ToolSpec,
)
from schemarouter.amendment import validate_amendment


def _tool() -> ToolSpec:
    return ToolSpec(
        name="materials",
        namespace="lab",
        description="Materials records",
        provider="internal",
        access_mode="python",
        source_type="calculated",
        endpoints=[
            EndpointSpec(
                name="current",
                description="Current record",
                method="GET",
                path="/materials/{material_id}",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="material_id",
                        required=True,
                        json_schema={"type": "string"},
                    )
                ],
                output_fields=[
                    FieldSpec(name="band_gap", json_schema={"type": "number"}),
                ],
                output_schema={"type": "object"},
            )
        ],
    )


def _with_endpoint(tool: ToolSpec, endpoint: EndpointSpec) -> ToolSpec:
    return tool.model_copy(update={"endpoints": [endpoint]})


def _endpoint(tool: ToolSpec) -> EndpointSpec:
    return tool.endpoints[0]


# --- accepted ---------------------------------------------------------------


def test_declaring_a_field_the_source_never_published_is_allowed():
    current = _tool()
    endpoint = _endpoint(current)
    amended = _with_endpoint(
        current,
        endpoint.model_copy(
            update={
                "output_fields": [
                    *endpoint.output_fields,
                    FieldSpec(name="formation_energy", unit="eV/atom"),
                ]
            }
        ),
    )
    validate_amendment(current, amended)


def test_annotating_an_existing_field_is_allowed():
    current = _tool()
    endpoint = _endpoint(current)
    annotated = endpoint.output_fields[0].model_copy(
        update={
            "semantic_id": "materials.band_gap",
            "aliases": ["band gap"],
            "unit": "eV",
            "qualifiers": {"method": "measured"},
            "identifier": False,
            "source_type": "experimental",
            "license": "CC-BY-4.0",
            "description": "Measured band gap",
        }
    )
    amended = _with_endpoint(
        current, endpoint.model_copy(update={"output_fields": [annotated]})
    )
    validate_amendment(current, amended)


def test_annotating_the_endpoint_description_and_aliases_is_allowed():
    current = _tool()
    endpoint = _endpoint(current)
    amended = _with_endpoint(
        current,
        endpoint.model_copy(
            update={"description": "Current certified record", "operation_aliases": ["fetch"]}
        ),
    )
    validate_amendment(current, amended)


def test_an_unchanged_spec_is_allowed():
    current = _tool()
    validate_amendment(current, current.model_copy(deep=True))


# --- refused: execution identity -------------------------------------------


@pytest.mark.parametrize(
    "update",
    [
        {"path": "/materials/all"},
        {"method": "POST"},
        {"read_only": False},
        {"destructive": True},
        {"execution_metadata": {"timeout": 5}},
        {"name": "renamed"},
    ],
    ids=["path", "method", "read_only", "destructive", "execution_metadata", "rename"],
)
def test_execution_identity_changes_are_refused(update):
    current = _tool()
    amended = _with_endpoint(current, _endpoint(current).model_copy(update=update))
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


def test_adding_a_parameter_is_refused():
    current = _tool()
    endpoint = _endpoint(current)
    amended = _with_endpoint(
        current,
        endpoint.model_copy(
            update={
                "parameters": [
                    *endpoint.parameters,
                    ParameterSpec(name="verbose", json_schema={"type": "boolean"}),
                ]
            }
        ),
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


def test_widening_the_input_schema_is_refused():
    current = _tool()
    amended = _with_endpoint(
        current,
        _endpoint(current).model_copy(update={"input_schema": {"type": "object"}}),
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


def test_changing_server_projection_is_refused():
    from schemarouter import ServerProjectionSpec

    current = _tool()
    amended = _with_endpoint(
        current,
        _endpoint(current).model_copy(
            update={"server_projection": ServerProjectionSpec(parameter="fields")}
        ),
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


# --- refused: validation shape ---------------------------------------------


def test_changing_a_published_field_json_schema_is_refused():
    # executor.py:1113-1135 validates the projected value against this schema;
    # relaxing it weakens raw-response validation.
    current = _tool()
    endpoint = _endpoint(current)
    relaxed = endpoint.output_fields[0].model_copy(update={"json_schema": {}})
    amended = _with_endpoint(
        current, endpoint.model_copy(update={"output_fields": [relaxed]})
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


def test_changing_the_output_schema_is_refused():
    current = _tool()
    amended = _with_endpoint(
        current,
        _endpoint(current).model_copy(update={"output_schema": {}}),
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


# --- refused: removal and shape --------------------------------------------


def test_removing_a_published_field_is_refused():
    current = _tool()
    amended = _with_endpoint(
        current, _endpoint(current).model_copy(update={"output_fields": []})
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


def test_adding_or_removing_an_endpoint_is_refused():
    current = _tool()
    extra = _endpoint(current).model_copy(update={"name": "history"})
    with pytest.raises(ContractAmendmentError):
        validate_amendment(
            current, current.model_copy(update={"endpoints": [_endpoint(current), extra]})
        )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, current.model_copy(update={"endpoints": []}))


@pytest.mark.parametrize(
    "update",
    [
        {"provider": "external"},
        {"access_mode": "http"},
        {"namespace": "other"},
        {"name": "renamed"},
        {"remote": True},
        {"source_type": "measured"},
    ],
    ids=["provider", "access_mode", "namespace", "name", "remote", "source_type"],
)
def test_tool_identity_changes_are_refused(update):
    current = _tool()
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, current.model_copy(update=update))


# --- error quality ----------------------------------------------------------


def test_the_refusal_names_every_violation_and_where():
    current = _tool()
    endpoint = _endpoint(current)
    broken_field = endpoint.output_fields[0].model_copy(update={"json_schema": {}})
    amended = _with_endpoint(
        current,
        endpoint.model_copy(update={"path": "/elsewhere", "output_fields": [broken_field]}),
    )
    with pytest.raises(ContractAmendmentError) as excinfo:
        validate_amendment(current, amended)
    message = str(excinfo.value)
    assert "path" in message
    assert "json_schema" in message
    assert "band_gap" in message
    assert "current" in message


def test_an_unrecognised_future_aspect_fails_closed(monkeypatch):
    # A field added to EndpointSpec later must default to frozen, not to
    # silently amendable.
    from schemarouter import amendment

    monkeypatch.setattr(
        amendment, "AMENDABLE_ENDPOINT_ASPECTS", frozenset({"operation_aliases"})
    )
    current = _tool()
    amended = _with_endpoint(
        current, _endpoint(current).model_copy(update={"description": "changed"})
    )
    with pytest.raises(ContractAmendmentError):
        validate_amendment(current, amended)


# --- binding bookkeeping ----------------------------------------------------


class _RestampRecord(BaseModel):
    band_gap: float
    note: str


def _bound_router():
    from schemarouter import SchemaRouter, schema_tool

    @schema_tool(read_only=True)
    def materials(material_id: str) -> _RestampRecord:
        """Return the current materials record."""
        return _RestampRecord(band_gap=1.1, note="internal")

    router = SchemaRouter()
    return router, router.add_callable(materials)


def test_restamp_points_an_existing_binding_at_the_current_fingerprint():
    router, key = _bound_router()
    tool = router.registry.get(key)
    endpoint = tool.endpoints[0]
    amended_endpoint = endpoint.model_copy(update={"description": "annotated"})
    router.add_tool(tool.model_copy(update={"endpoints": [amended_endpoint]}), replace=True)

    assert not router.executor.is_binding_ready_for_contract(
        key, router.registry.get(key).fingerprint
    )
    assert router.executor.restamp_binding(key) is True
    assert router.executor.is_binding_ready_for_contract(
        key, router.registry.get(key).fingerprint
    )


def test_restamp_reports_false_when_there_is_no_binding():
    router, key = _bound_router()
    router.executor.unbind(key)
    assert router.executor.restamp_binding(key) is False


def test_restamp_does_not_expose_or_accept_an_invoker():
    router, key = _bound_router()
    public = [name for name in dir(router.executor) if not name.startswith("_")]
    assert not [name for name in public if "invoker" in name.lower()]
    import inspect

    signature = inspect.signature(router.executor.restamp_binding)
    assert list(signature.parameters) == ["tool_key"]


# --- public API -------------------------------------------------------------


def _declaring_router():
    """A router whose tool publishes no output declarations, like most MCP servers."""
    from schemarouter import EndpointSpec, ParameterSpec, SchemaRouter, ToolSpec

    router = SchemaRouter()
    key = router.add_tool(
        ToolSpec(
            name="remote",
            provider="external",
            access_mode="mcp",
            source_type="measured",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    description="Look up a material",
                    read_only=True,
                    destructive=False,
                    parameters=[
                        ParameterSpec(
                            name="material_id",
                            required=True,
                            json_schema={"type": "string"},
                        )
                    ],
                )
            ],
        )
    )
    return router, key


def test_amending_declares_fields_and_keeps_the_capability_executable():
    from schemarouter import PlanRequest

    router, key = _bound_router()
    tool = router.registry.get(key)
    endpoint = tool.endpoints[0]
    annotated = [
        field.model_copy(update={"semantic_id": f"materials.{field.name}"})
        for field in endpoint.output_fields
    ]
    amended = tool.model_copy(
        update={"endpoints": [endpoint.model_copy(update={"output_fields": annotated})]}
    )

    assert router.amend_capability(key, amended) == key
    results = router.invoke(
        PlanRequest(query="materials band gap", arguments={"material_id": "M1"})
    )
    assert results, "the amended capability must still be executable"


def test_a_capability_with_no_declarations_can_receive_them():
    from schemarouter import FieldSpec

    router, key = _declaring_router()
    tool = router.registry.get(key)
    endpoint = tool.endpoints[0]
    assert endpoint.output_fields == []

    amended = tool.model_copy(
        update={
            "endpoints": [
                endpoint.model_copy(
                    update={
                        "output_fields": [
                            FieldSpec(
                                name="band_gap",
                                semantic_id="materials.band_gap",
                                unit="eV",
                                qualifiers={"method": "measured"},
                            )
                        ]
                    }
                )
            ]
        }
    )
    router.amend_capability(key, amended)
    declared = router.registry.get(key).endpoints[0].output_fields
    assert [field.name for field in declared] == ["band_gap"]
    assert declared[0].unit == "eV"


def test_a_refused_amendment_changes_nothing():
    router, key = _bound_router()
    before = router.registry.get(key)
    amended = before.model_copy(
        update={"endpoints": [before.endpoints[0].model_copy(update={"read_only": False})]}
    )

    with pytest.raises(ContractAmendmentError):
        router.amend_capability(key, amended)

    assert router.registry.get(key).fingerprint == before.fingerprint
    assert router.executor.is_binding_ready_for_contract(key, before.fingerprint)


def test_amending_an_unregistered_key_is_refused():
    router, _ = _bound_router()
    tool = router.registry.get(router.registry.keys()[0])
    with pytest.raises(KeyError):
        router.amend_capability("lab.absent", tool)


def test_a_plan_built_before_the_amendment_is_still_rejected():
    # Staleness protection must survive the amendment path, or drift detection
    # would be weaker for amended capabilities than for any other. There is no
    # `router.execute(plan)`; a prebuilt call is re-checked with
    # `executor.validate_call`, which is what the execution path itself uses.
    from schemarouter import PlanRequest, SchemaDriftError

    router, key = _bound_router()
    stale_plan = router.plan(
        PlanRequest(query="materials band gap", arguments={"material_id": "M1"})
    )
    assert stale_plan.calls, "the fixture must produce a call to make this test meaningful"
    stale_call = stale_plan.calls[0]
    router.executor.validate_call(stale_call)  # valid before the amendment

    tool = router.registry.get(key)
    endpoint = tool.endpoints[0]
    amended = tool.model_copy(
        update={"endpoints": [endpoint.model_copy(update={"description": "annotated"})]}
    )
    router.amend_capability(key, amended)

    with pytest.raises(SchemaDriftError):
        router.executor.validate_call(stale_call)


def test_the_amendment_path_is_not_reachable_from_model_facing_code():
    # A decision backend receives finite option IDs, never a router. Assert the
    # amendment API never leaked into the decision or planner surfaces.
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "schemarouter"
    for name in ("decisions.py", "decision_policy.py", "planner.py", "pairwise.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "amend_capability" not in text, name
        assert "restamp_binding" not in text, name

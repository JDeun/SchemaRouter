from schemarouter.capability_lineage import (
    CapabilityLineageHop,
    build_capability_lineage,
)


def test_lineage_id_is_deterministic() -> None:
    selected = CapabilityLineageHop(
        provider="materials-project",
        access_method="rest",
        route_id="mp.summary",
        capability_id="material.summary",
        schema_revision="v1",
        schema_fingerprint="abc",
        semantic_ids=("band_gap", "formula"),
    )

    first = build_capability_lineage(selected=selected)
    second = build_capability_lineage(selected=selected)

    assert first == second
    assert first.lineage_id == second.lineage_id


def test_lineage_distinguishes_selected_and_actual_fallback() -> None:
    selected = CapabilityLineageHop(
        provider="provider-a",
        access_method="rest",
        route_id="a.energy",
        reason="selected",
    )
    fallback = CapabilityLineageHop(
        provider="provider-a",
        access_method="mcp",
        route_id="a.mcp.energy",
        reason="method_unhealthy",
    )

    lineage = build_capability_lineage(
        selected=selected,
        actual=fallback,
        fallbacks=[fallback],
    )

    assert lineage.selected.route_id == "a.energy"
    assert lineage.actual.route_id == "a.mcp.energy"
    assert lineage.fallbacks[0].reason == "method_unhealthy"


def test_lineage_schema_excludes_payload_and_credentials() -> None:
    fields = set(CapabilityLineageHop.model_fields)
    assert "payload" not in fields
    assert "arguments" not in fields
    assert "credentials" not in fields
    assert "headers" not in fields

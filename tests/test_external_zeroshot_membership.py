# ruff: noqa: E402, I001
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec

from benchmarks.external_zeroshot_membership import (  # noqa: E402
    HYPOTHESIS_TEMPLATE,
    LEAF_LABELS,
    OUTSIDE_LABEL,
    ExternalZeroShotMembershipRouter,
    capability_labels,
    compile_registry_contracts,
    decide_membership,
)
from benchmarks.operation_routing_v5f_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def test_candidate_labels_are_fixed_and_outside_is_last() -> None:
    labels = capability_labels({"update", "retrieve"})
    assert labels == [
        LEAF_LABELS["retrieve"],
        LEAF_LABELS["update"],
        OUTSIDE_LABEL,
    ]
    assert HYPOTHESIS_TEMPLATE == "The user wants to {}."


def test_outside_label_only_vetoes() -> None:
    veto, reason = decide_membership(
        top_label=OUTSIDE_LABEL,
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )
    assert veto is True
    assert reason == "outside_label_top1"

    veto, reason = decide_membership(
        top_label=LEAF_LABELS["update"],
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )
    assert veto is False
    assert reason == "supported_label_top1"


def test_unknown_endpoint_semantics_disable_veto() -> None:
    veto, reason = decide_membership(
        top_label=OUTSIDE_LABEL,
        supported_leaves={"retrieve"},
        tool_has_unknown=True,
    )
    assert veto is False
    assert reason == "unknown_endpoint_semantics_preserve"


def test_compiler_covers_native_openapi_mcp_and_typed_units() -> None:
    contracts = compile_registry_contracts(development_registry())
    assert {contract.adapter or "native" for contract in contracts.values()} == {
        "native",
        "openapi",
        "mcp",
    }
    assert contracts["permits_api.p17"].leaf == "retrieve"
    assert contracts["permits_api.p28"].leaf == "update"
    assert contracts["permits_api.p39"].leaf == "delete"
    assert contracts["knowledge_ops.k17"].leaf == "search"
    assert contracts["knowledge_ops.k28"].leaf == "retrieve"
    assert contracts["knowledge_ops.k39"].leaf == "list"

    current = contracts["temperature.current"]
    field = next(
        item
        for item in current.data_contract
        if item.get("name") == "temperature"
    )
    assert field["type"] == "number"
    assert field["semantic_id"] == "environment.temperature"
    assert field["source_unit"] == "degC"
    assert field["canonical_unit"] == "K"
    assert field["dimension"] == "temperature"
    assert field["scale"] == 1.0
    assert field["offset"] == 273.15
    assert field["qualifiers"] == {"statistic": "instantaneous"}


def test_confirmation_typed_pressure_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(confirmation_registry())
    field = next(
        item
        for item in contracts["pressure.current"].data_contract
        if item.get("name") == "pressure"
    )
    assert field["type"] == "number"
    assert field["source_unit"] == "kPa"
    assert field["canonical_unit"] == "Pa"
    assert field["dimension"] == "pressure"
    assert field["scale"] == 1000.0


def _two_route_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo records",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one existing record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="update",
                    description="Update an existing record",
                    read_only=False,
                ),
            ],
        )
    )
    return registry


def _fake_embedder():
    calls = {"count": 0}

    def embed(texts: list[str]) -> list[list[float]]:
        calls["count"] += 1
        if calls["count"] == 1:
            assert len(texts) == 4
            return [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ]
        assert len(texts) == 1
        return [[1.0, 0.0]]

    return embed


def test_external_supported_label_cannot_switch_raw_positive_route() -> None:
    seen: dict[str, object] = {}

    def classifier(query: str, labels: list[str], template: str):
        seen["query"] = query
        seen["labels"] = labels
        seen["template"] = template
        return {
            "top_label": LEAF_LABELS["update"],
            "scores": {
                LEAF_LABELS["update"]: 0.9,
                LEAF_LABELS["retrieve"]: 0.08,
                OUTSIDE_LABEL: 0.02,
            },
        }

    router = ExternalZeroShotMembershipRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("show record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["zero_shot_top_label"] == LEAF_LABELS["update"]
    assert result["predicted"] == "demo.retrieve"
    assert seen["template"] == HYPOTHESIS_TEMPLATE


def test_external_outside_label_can_only_abstain() -> None:
    def classifier(query: str, labels: list[str], template: str):
        return {"top_label": OUTSIDE_LABEL, "scores": {OUTSIDE_LABEL: 1.0}}

    router = ExternalZeroShotMembershipRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("delete record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] is None
    assert result["veto_reason"] == "outside_label_top1"


def test_unknown_endpoint_semantics_skip_classifier_entirely() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="opaque",
            description="Opaque capability",
            endpoints=[
                EndpointSpec(
                    name="x17",
                    description="",
                    read_only=None,
                    destructive=None,
                )
            ],
        )
    )

    def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    calls = {"count": 0}

    def classifier(query: str, labels: list[str], template: str):
        calls["count"] += 1
        return {"top_label": OUTSIDE_LABEL}

    router = ExternalZeroShotMembershipRouter(registry, embed, classifier)
    result = router.route("do something")
    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert calls["count"] == 0


def test_behavior_source_contains_no_evaluation_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "external_zeroshot_membership.py"
    ).read_text()
    for forbidden in (
        "permits_api.p17",
        "knowledge_ops.k17",
        "applications_api.a17",
        "evidence_ops.e17",
        "shipments.status",
        "profiles_api.r17",
    ):
        assert forbidden not in source

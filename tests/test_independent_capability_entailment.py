from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.independent_capability_entailment import (  # noqa: E402
    LEAF_LABELS,
    IndependentCapabilityEntailmentRouter,
    capability_hypotheses,
    compile_registry_contracts,
    decide_entailments,
)
from benchmarks.operation_routing_v5h_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_capability_hypotheses_are_independent_and_ordered() -> None:
    pairs = capability_hypotheses({"update", "retrieve"})
    assert pairs == [
        (
            "retrieve",
            f"The user wants to {LEAF_LABELS['retrieve']}.",
        ),
        (
            "update",
            f"The user wants to {LEAF_LABELS['update']}.",
        ),
    ]


def test_independent_entailment_rule_is_threshold_free() -> None:
    veto, reason = decide_entailments(
        top_labels=["not_entailment", "entailment"],
        tool_has_unknown=False,
    )
    assert veto is False
    assert reason == "at_least_one_entailment_preserve"

    veto, reason = decide_entailments(
        top_labels=["not_entailment", "not_entailment"],
        tool_has_unknown=False,
    )
    assert veto is True
    assert reason == "all_not_entailment_veto"


def test_unknown_endpoint_semantics_disable_veto() -> None:
    veto, reason = decide_entailments(
        top_labels=["not_entailment"],
        tool_has_unknown=True,
    )
    assert veto is False
    assert reason == "unknown_endpoint_semantics_preserve"


def test_compiler_covers_native_openapi_and_mcp() -> None:
    contracts = compile_registry_contracts(development_registry())
    assert {contract.adapter or "native" for contract in contracts.values()} == {
        "native",
        "openapi",
        "mcp",
    }
    assert contracts["certificate_records_api.z17"].leaf == "retrieve"
    assert contracts["certificate_records_api.z28"].leaf == "update"
    assert contracts["certificate_records_api.z39"].leaf == "delete"
    assert contracts["reference_index_ops.i17"].leaf == "search"
    assert contracts["reference_index_ops.i28"].leaf == "retrieve"
    assert contracts["reference_index_ops.i39"].leaf == "list"


def test_development_typed_unit_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(development_registry())
    field = next(
        item
        for item in contracts["density_probe.current"].data_contract
        if item.get("name") == "density"
    )
    assert field["type"] == "number"
    assert field["semantic_id"] == "materials.density"
    assert field["source_unit"] == "kg/m3"
    assert field["canonical_unit"] == "g/cm3"
    assert field["dimension"] == "density"
    assert field["scale"] == 0.001
    assert field["offset"] == 0.0


def test_confirmation_typed_unit_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(confirmation_registry())
    field = next(
        item
        for item in contracts["mass_probe.current"].data_contract
        if item.get("name") == "mass"
    )
    assert field["type"] == "number"
    assert field["semantic_id"] == "physical.mass"
    assert field["source_unit"] == "g"
    assert field["canonical_unit"] == "kg"
    assert field["dimension"] == "mass"
    assert field["scale"] == 0.001
    assert field["offset"] == 0.0


def _two_route_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="Demo records",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one already-identified existing record",
                    read_only=True,
                ),
                EndpointSpec(
                    name="update",
                    description="Update fields on an existing record",
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
        assert texts
        return [[1.0, 0.0] for _ in texts]

    return embed


def test_any_entailed_capability_preserves_raw_positive_route() -> None:
    seen: dict[str, object] = {}

    def classifier(premise: str, hypotheses: list[str]):
        seen["premise"] = premise
        seen["hypotheses"] = hypotheses
        return {
            "judgments": [
                {
                    "top_label": "entailment",
                    "scores": {"entailment": 0.8, "not_entailment": 0.2},
                },
                {
                    "top_label": "not_entailment",
                    "scores": {"entailment": 0.1, "not_entailment": 0.9},
                },
            ]
        }

    router = IndependentCapabilityEntailmentRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("show record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] == "demo.retrieve"
    assert result["entailed_leaf_count"] == 1
    assert len(seen["hypotheses"]) == 2


def test_all_not_entailment_can_only_abstain() -> None:
    def classifier(premise: str, hypotheses: list[str]):
        return {
            "judgments": [
                {"top_label": "not_entailment"},
                {"top_label": "not_entailment"},
            ]
        }

    router = IndependentCapabilityEntailmentRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("delete record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] is None
    assert result["veto_reason"] == "all_not_entailment_veto"


def test_unknown_endpoint_semantics_skip_nli_call() -> None:
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

    def classifier(premise: str, hypotheses: list[str]):
        calls["count"] += 1
        return {"judgments": []}

    router = IndependentCapabilityEntailmentRouter(registry, embed, classifier)
    result = router.route("do something")

    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert calls["count"] == 0


def test_behavior_source_contains_no_evaluation_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "independent_capability_entailment.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "certificate_records_api.z17",
        "reference_index_ops.i17",
        "approval_records_api.u17",
        "specimen_index_ops.s17",
        "license_records_api.l17",
        "permits_api.p17",
    ):
        assert forbidden not in source

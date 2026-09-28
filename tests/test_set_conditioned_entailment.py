from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v5g_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.set_conditioned_entailment import (  # noqa: E402
    LEAF_LABELS,
    SetConditionedEntailmentRouter,
    capability_hypothesis,
    compile_registry_contracts,
    decide_entailment,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_capability_hypothesis_is_ordered_and_set_conditioned() -> None:
    hypothesis = capability_hypothesis({"update", "retrieve"})
    assert hypothesis == (
        "The requested operation is one of the following registered operations: "
        f"{LEAF_LABELS['retrieve']}; {LEAF_LABELS['update']}."
    )


def test_binary_entailment_rule_is_threshold_free() -> None:
    veto, reason = decide_entailment(
        top_label="entailment",
        tool_has_unknown=False,
    )
    assert veto is False
    assert reason == "entailment_preserve"

    veto, reason = decide_entailment(
        top_label="not_entailment",
        tool_has_unknown=False,
    )
    assert veto is True
    assert reason == "not_entailment_veto"


def test_unknown_endpoint_semantics_disable_nli_veto() -> None:
    veto, reason = decide_entailment(
        top_label="not_entailment",
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
    assert contracts["license_records_api.l17"].leaf == "retrieve"
    assert contracts["license_records_api.l28"].leaf == "update"
    assert contracts["license_records_api.l39"].leaf == "delete"
    assert contracts["knowledge_corpus_ops.c17"].leaf == "search"
    assert contracts["knowledge_corpus_ops.c28"].leaf == "retrieve"
    assert contracts["knowledge_corpus_ops.c39"].leaf == "list"


def test_development_typed_unit_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(development_registry())
    field = next(
        item
        for item in contracts["humidity_probe.current"].data_contract
        if item.get("name") == "relative_humidity"
    )

    assert field["type"] == "number"
    assert field["semantic_id"] == "environment.relative_humidity"
    assert field["source_unit"] == "percent"
    assert field["canonical_unit"] == "1"
    assert field["dimension"] == "relative_humidity"
    assert field["scale"] == 0.01
    assert field["offset"] == 0.0
    assert field["qualifiers"] == {"statistic": "instantaneous"}


def test_confirmation_typed_unit_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(confirmation_registry())
    field = next(
        item
        for item in contracts["velocity_probe.current"].data_contract
        if item.get("name") == "velocity"
    )

    assert field["type"] == "number"
    assert field["semantic_id"] == "motion.velocity"
    assert field["source_unit"] == "km/h"
    assert field["canonical_unit"] == "m/s"
    assert field["dimension"] == "speed"
    assert field["scale"] == 0.2777777777777778
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


def test_entailment_preserves_raw_positive_route() -> None:
    seen: dict[str, str] = {}

    def classifier(premise: str, hypothesis: str):
        seen["premise"] = premise
        seen["hypothesis"] = hypothesis
        return {
            "top_label": "entailment",
            "scores": {"entailment": 0.8, "not_entailment": 0.2},
        }

    router = SetConditionedEntailmentRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("show record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] == "demo.retrieve"
    assert seen["premise"] == "show record R-1"
    assert LEAF_LABELS["retrieve"] in seen["hypothesis"]
    assert LEAF_LABELS["update"] in seen["hypothesis"]


def test_not_entailment_can_only_abstain() -> None:
    def classifier(premise: str, hypothesis: str):
        return {
            "top_label": "not_entailment",
            "scores": {"entailment": 0.1, "not_entailment": 0.9},
        }

    router = SetConditionedEntailmentRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("delete record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] is None
    assert result["veto_reason"] == "not_entailment_veto"


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

    def classifier(premise: str, hypothesis: str):
        calls["count"] += 1
        return {"top_label": "not_entailment"}

    router = SetConditionedEntailmentRouter(registry, embed, classifier)
    result = router.route("do something")

    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert calls["count"] == 0


def test_behavior_source_contains_no_evaluation_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "set_conditioned_entailment.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "license_records_api.l17",
        "knowledge_corpus_ops.c17",
        "registration_records_api.r17",
        "archive_catalog_ops.a17",
        "permits_api.p17",
        "shipments.status",
    ):
        assert forbidden not in source

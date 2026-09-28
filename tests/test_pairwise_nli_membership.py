from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v5h_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)
from benchmarks.pairwise_nli_membership import (  # noqa: E402
    ALL_LEAF_ORDER,
    LEAF_LABELS,
    PairwiseNliMembershipRouter,
    compile_registry_contracts,
    decide_pairwise_membership,
    leaf_hypotheses,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_leaf_hypothesis_universe_is_fixed() -> None:
    hypotheses = leaf_hypotheses()

    assert tuple(hypotheses) == ALL_LEAF_ORDER
    assert len(hypotheses) == 22
    assert hypotheses["retrieve"] == (
        f"The user wants to {LEAF_LABELS['retrieve']}."
    )
    assert hypotheses["chat"] == (
        f"The user wants to {LEAF_LABELS['chat']}."
    )


def _scores(default: float = 0.1) -> dict[str, float]:
    return {leaf: default for leaf in ALL_LEAF_ORDER}


def test_counterfactual_max_strictly_greater_vetoes() -> None:
    scores = _scores()
    scores["retrieve"] = 0.7
    scores["delete"] = 0.8

    result = decide_pairwise_membership(
        entailment_scores=scores,
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )

    assert result["veto"] is True
    assert result["supported_leaf"] == "retrieve"
    assert result["counterfactual_leaf"] == "delete"
    assert result["reason"] == "counterfactual_max_exceeds_supported_max"


def test_supported_max_greater_preserves() -> None:
    scores = _scores()
    scores["retrieve"] = 0.9
    scores["delete"] = 0.8

    result = decide_pairwise_membership(
        entailment_scores=scores,
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )

    assert result["veto"] is False
    assert result["reason"] == "supported_max_greater_or_equal"


def test_exact_tie_preserves_raw_authority() -> None:
    scores = _scores()
    scores["retrieve"] = 0.8
    scores["delete"] = 0.8

    result = decide_pairwise_membership(
        entailment_scores=scores,
        supported_leaves={"retrieve"},
        tool_has_unknown=False,
    )

    assert result["veto"] is False
    assert result["supported_score"] == result["counterfactual_score"]


def test_unknown_endpoint_semantics_disable_veto() -> None:
    result = decide_pairwise_membership(
        entailment_scores={},
        supported_leaves=set(),
        tool_has_unknown=True,
    )

    assert result["veto"] is False
    assert result["reason"] == "unknown_endpoint_semantics_preserve"


def test_compiler_covers_native_openapi_mcp_and_units() -> None:
    contracts = compile_registry_contracts(development_registry())

    assert {contract.adapter or "native" for contract in contracts.values()} == {
        "native",
        "openapi",
        "mcp",
    }
    assert contracts["certificate_records_api.crt17"].leaf == "retrieve"
    assert contracts["certificate_records_api.crt28"].leaf == "update"
    assert contracts["certificate_records_api.crt39"].leaf == "delete"
    assert contracts["specimen_index_ops.sp17"].leaf == "search"
    assert contracts["specimen_index_ops.sp28"].leaf == "retrieve"
    assert contracts["specimen_index_ops.sp39"].leaf == "list"

    field = next(
        item
        for item in contracts["flow_probe.current"].data_contract
        if item.get("name") == "flow_rate"
    )
    assert field["type"] == "number"
    assert field["semantic_id"] == "process.flow_rate"
    assert field["source_unit"] == "mL/s"
    assert field["canonical_unit"] == "L/s"
    assert field["dimension"] == "volumetric_flow_rate"
    assert field["scale"] == 0.001


def test_confirmation_power_contract_is_preserved() -> None:
    contracts = compile_registry_contracts(confirmation_registry())
    field = next(
        item
        for item in contracts["power_probe.current"].data_contract
        if item.get("name") == "power"
    )

    assert field["type"] == "number"
    assert field["semantic_id"] == "energy.power"
    assert field["source_unit"] == "W"
    assert field["canonical_unit"] == "kW"
    assert field["dimension"] == "power"
    assert field["scale"] == 0.001


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
        return [[1.0, 0.0] for _ in texts]

    return embed


def test_nli_can_only_veto_raw_positive_route() -> None:
    def classifier(
        premise: str,
        hypotheses: dict[str, str],
    ) -> dict[str, object]:
        scores = {leaf: 0.1 for leaf in hypotheses}
        scores["retrieve"] = 0.7
        scores["delete"] = 0.9
        return {"entailment_scores": scores}

    router = PairwiseNliMembershipRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("delete record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["predicted"] is None
    assert result["top_counterfactual_leaf"] == "delete"


def test_supported_nli_evidence_cannot_switch_endpoint() -> None:
    def classifier(
        premise: str,
        hypotheses: dict[str, str],
    ) -> dict[str, object]:
        scores = {leaf: 0.1 for leaf in hypotheses}
        scores["update"] = 0.95
        scores["retrieve"] = 0.8
        return {"entailment_scores": scores}

    router = PairwiseNliMembershipRouter(
        _two_route_registry(),
        _fake_embedder(),
        classifier,
    )
    result = router.route("update record R-1")

    assert result["raw_top_route"] == "demo.retrieve"
    assert result["top_supported_leaf"] == "update"
    assert result["predicted"] == "demo.retrieve"


def test_unknown_endpoint_semantics_skip_nli_batch() -> None:
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

    def classifier(
        premise: str,
        hypotheses: dict[str, str],
    ) -> dict[str, object]:
        calls["count"] += 1
        return {"entailment_scores": _scores()}

    router = PairwiseNliMembershipRouter(registry, embed, classifier)
    result = router.route("do something")

    assert result["predicted"] == "opaque.x17"
    assert result["tool_has_unknown_leaf"] is True
    assert calls["count"] == 0


def test_behavior_source_contains_no_evaluation_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "pairwise_nli_membership.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "certificate_records_api.crt17",
        "specimen_index_ops.sp17",
        "authorization_records_api.auth17",
        "dataset_index_ops.ds17",
        "license_records_api.l17",
        "permits_api.p17",
    ):
        assert forbidden not in source

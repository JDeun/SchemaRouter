from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6g_catalog import development_registry  # noqa: E402
from benchmarks.schema_cross_encoder_membership import (  # noqa: E402
    BACKGROUND_DOCUMENTS,
    RelativeCrossEncoderCapabilityGate,
    compile_tool_evidence_banks,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec  # noqa: E402


def test_v6g_evidence_banks_are_registry_grounded_and_complete() -> None:
    registry = development_registry()
    first, first_unknown = compile_tool_evidence_banks(registry)
    second, second_unknown = compile_tool_evidence_banks(registry)

    assert first == second
    assert not first_unknown
    assert not second_unknown
    assert len(first) == 7
    assert sum(len(bank.supported) for bank in first.values()) == 19
    assert len(BACKGROUND_DOCUMENTS) == 16
    assert all(bank.complement for bank in first.values())
    assert all(
        document.kind == "supported"
        for bank in first.values()
        for document in bank.supported
    )
    assert all(
        document.kind == "complement"
        for bank in first.values()
        for document in bank.complement
    )


def _demo_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="records",
            description="Record service",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve one identified record",
                    operation_aliases=["retrieve"],
                    read_only=True,
                ),
                EndpointSpec(
                    name="delete",
                    description="Delete one identified record",
                    operation_aliases=["delete"],
                    destructive=True,
                    read_only=False,
                ),
            ],
        )
    )
    return registry


def _bge_embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lower = text.lower()
        if "delete" in lower:
            vectors.append([0.0, 1.0])
        else:
            vectors.append([1.0, 0.0])
    return vectors


def test_v6g_preserves_raw_winner_when_supported_wins() -> None:
    def scorer(query: str, docs: list[str]) -> list[float]:
        return [
            5.0 if "operation: retrieve" in doc else 1.0
            for doc in docs
        ]

    gate = RelativeCrossEncoderCapabilityGate(
        _demo_registry(),
        bge_embedder=_bge_embed,
        pair_scorer=scorer,
    )
    result = gate.route("retrieve record R-1")
    assert result["raw_top_route"] == "records.retrieve"
    assert result["predicted"] == "records.retrieve"
    assert result["negative_advantage"] <= 0.0


def test_v6g_vetoes_when_counterfactual_outscores_supported() -> None:
    def scorer(query: str, docs: list[str]) -> list[float]:
        return [
            9.0 if doc.startswith("counterfactual capability") else 1.0
            for doc in docs
        ]

    gate = RelativeCrossEncoderCapabilityGate(
        _demo_registry(),
        bge_embedder=_bge_embed,
        pair_scorer=scorer,
    )
    result = gate.route("retrieve record R-1")
    assert result["raw_top_route"] == "records.retrieve"
    assert result["predicted"] is None
    assert result["negative_source"] == "complement"


def test_v6g_exact_tie_preserves_raw_route() -> None:
    def scorer(query: str, docs: list[str]) -> list[float]:
        return [2.0 for _ in docs]

    gate = RelativeCrossEncoderCapabilityGate(
        _demo_registry(),
        bge_embedder=_bge_embed,
        pair_scorer=scorer,
    )
    result = gate.route("retrieve record R-1")
    assert result["predicted"] == result["raw_top_route"]
    assert result["negative_advantage"] == 0.0

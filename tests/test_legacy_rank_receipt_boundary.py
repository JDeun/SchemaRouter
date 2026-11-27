"""Research ranking receipts must stay distinct from installed paper receipts."""
from dataclasses import asdict, fields, replace
from typing import get_args, get_type_hints

import pytest

from schemarouter import IndexedNativeFieldResult, NativeIndexedGraphResult
from schemarouter.native_graph_index import (
    NativeIndexedGraphCandidate,
    NativeIndexedTwoHopCandidate,
    NativeIndexedTwoHopResult,
)
from scripts.research_legacy_fork_arm import NativeIndexedGraphResult as HistoricalForkArmResult
from scripts.research_legacy_g5_rank import NativeIndexedGraphResult as HistoricalGraphResult
from scripts.research_legacy_graph_candidates import (
    NativeIndexedGraphCandidate as HistoricalGraphCandidate,
)
from scripts.research_legacy_graph_candidates import (
    NativeIndexedTwoHopCandidate as HistoricalTwoHopCandidate,
)
from scripts.research_legacy_graph_rank import NativeIndexedGraphResult as HistoricalOwnerRankResult
from scripts.research_legacy_graph_rank import NativeIndexedTwoHopResult as HistoricalTwoHopResult
from scripts.research_legacy_posting_rank import IndexedNativeFieldResult as HistoricalFieldResult


@pytest.mark.parametrize(
    ("product", "historical", "kwargs"),
    [
        (
            IndexedNativeFieldResult,
            HistoricalFieldResult,
            {"registry_version": 1, "index_snapshot_id": "snapshot", "requested_k": 5,
             "qualified_count": 7, "candidates": ()},
        ),
        (
            NativeIndexedGraphResult,
            HistoricalGraphResult,
            {"registry_version": 1, "index_snapshot_id": "snapshot", "requested_k": 5,
             "qualified_path_count": 7, "candidates": ()},
        ),
    ],
)
def test_historical_abstention_remains_a_distinct_non_product_receipt(
    product, historical, kwargs,
):
    receipt = historical(
        status="ranker_abstained_unverified", experimental_ranked=True, **kwargs,
    )
    assert type(receipt) is historical
    assert not isinstance(receipt, product)
    wire = asdict(receipt)
    assert wire["status"] == "ranker_abstained_unverified"
    assert wire["experimental_ranked"] is True
    assert historical(**wire) == receipt
    research_only = {"experimental_ranked"}
    if product is NativeIndexedGraphResult:
        research_only.update({
            "deterministic_paper_ranked", "independent_quality_evidence", "calibrated_no_fit",
        })
    assert tuple(field.name for field in fields(historical) if field.name not in research_only) == (
        tuple(field.name for field in fields(product))
    )
    assert "ranker_abstained_unverified" in get_args(get_type_hints(historical)["status"])
    assert "ranker_abstained_unverified" not in get_args(get_type_hints(product)["status"])
    with pytest.raises(TypeError):
        product(**wire)
    assert not receipt.deterministic_paper_ranked


def test_historical_fork_arm_receipt_is_not_a_product_result() -> None:
    receipt = HistoricalForkArmResult(
        status="internal_fork_arm", registry_version=1, index_snapshot_id="snapshot",
        requested_k=5, qualified_path_count=7, candidates=(),
    )
    assert type(receipt) is HistoricalForkArmResult
    assert not isinstance(receipt, NativeIndexedGraphResult)
    assert "internal_fork_arm" in get_args(get_type_hints(HistoricalForkArmResult)["status"])
    assert "internal_fork_arm" not in get_args(get_type_hints(NativeIndexedGraphResult)["status"])
    assert HistoricalForkArmResult(**asdict(receipt)) == receipt
    assert not receipt.executable_authority
    assert not receipt.deterministic_paper_ranked


def test_owner_ranked_graph_receipt_is_checkout_only() -> None:
    receipt = HistoricalOwnerRankResult(
        status="ranked_unverified", registry_version=1, index_snapshot_id="snapshot",
        requested_k=5, qualified_path_count=7, candidates=(),
        deterministic_paper_ranked=True,
    )
    assert not isinstance(receipt, NativeIndexedGraphResult)
    assert "ranked_unverified" not in get_args(get_type_hints(NativeIndexedGraphResult)["status"])
    assert "deterministic_paper_ranked" not in {f.name for f in fields(NativeIndexedGraphResult)}
    assert HistoricalOwnerRankResult(**asdict(receipt)) == receipt
    assert not receipt.executable_authority


@pytest.mark.parametrize(
    ("product", "historical", "kwargs", "counts"),
    [
        (
            NativeIndexedGraphCandidate,
            HistoricalGraphCandidate,
            {
                "producer_route_id": "root.read",
                "consumer_route_id": "target.read",
                "producer_tool_fingerprint": "t1",
                "producer_endpoint_fingerprint": "e1",
                "consumer_tool_fingerprint": "t2",
                "consumer_endpoint_fingerprint": "e2",
                "producer_identifier_field": "id",
                "consumer_required_parameter": "id",
                "consumer_output_fields": ("status",),
                "parameter_bindings": (("id", "id"),),
            },
            {"producer_visible_field_count": 3, "consumer_visible_field_count": 4},
        ),
        (
            NativeIndexedTwoHopCandidate,
            HistoricalTwoHopCandidate,
            {
                "route_ids": ("root.read", "middle.read", "target.read"),
                "route_fingerprints": (("t1", "e1"), ("t2", "e2"), ("t3", "e3")),
                "root_to_intermediate": (("id", "id"),),
                "intermediate_to_target": (("id2", "id2"),),
                "target_output_fields": ("status",),
                "source_root_parameters": (),
            },
            {"visible_field_counts": (3, 4, 5)},
        ),
    ],
)
def test_historical_graph_candidate_keeps_rank_counts_outside_product(
    product, historical, kwargs, counts,
) -> None:
    current = product(**kwargs)
    research = historical(**kwargs, **counts)
    assert type(current) is product
    assert type(research) is historical
    assert not isinstance(research, product)
    assert tuple(f.name for f in fields(historical) if f.name not in counts) == (
        tuple(f.name for f in fields(product))
    )
    assert asdict(research) == {**asdict(current), **counts}
    assert historical(**asdict(research)) == research
    assert replace(research) == research
    assert replace(research, **dict.fromkeys(counts)) == historical(**kwargs)
    assert research != historical(**kwargs)
    assert historical(**kwargs) != current
    assert counts.keys().isdisjoint(asdict(current))
    with pytest.raises(TypeError):
        product(**asdict(research))


@pytest.mark.parametrize(
    ("product", "historical"),
    [
        (NativeIndexedGraphResult, HistoricalOwnerRankResult),
        (NativeIndexedTwoHopResult, HistoricalTwoHopResult),
    ],
)
def test_product_graph_result_contains_no_research_quality_claims(product, historical):
    kwargs = {
        "status": "no_proven_hit",
        "index_snapshot_id": "snapshot",
        "registry_version": 1,
        "requested_k": 5,
        "qualified_path_count": 0,
        "candidates": (),
    }
    receipt = product(**kwargs)
    assert receipt.executable_authority is False
    assert asdict(receipt) == {**kwargs, "executable_authority": False}
    assert product(**asdict(receipt)) == receipt
    assert replace(receipt) == receipt
    research = historical(**kwargs)
    assert research.independent_quality_evidence is False
    assert research.calibrated_no_fit is False
    assert research.executable_authority is False
    for name in ("independent_quality_evidence", "calibrated_no_fit"):
        assert not hasattr(receipt, name)
        assert name not in get_type_hints(product)
        assert asdict(research)[name] is False
        with pytest.raises(TypeError):
            product(**kwargs, **{name: False})
    assert get_args(get_type_hints(product)["executable_authority"]) == (False,)
    for forged in (True, 1, 0, None, "false"):
        with pytest.raises(ValueError, match="cannot grant execution authority"):
            product(**kwargs, executable_authority=forged)
        with pytest.raises(ValueError, match="cannot grant execution authority"):
            replace(receipt, executable_authority=forged)

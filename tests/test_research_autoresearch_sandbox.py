"""Guard tests for proposed AutoResearch editable reranking sandbox (#1412)."""
from __future__ import annotations

import copy
import math

import pytest

from scripts.research_autoresearch_sandbox import (
    CandidateWorker,
    candidate_view,
    decide,
    evaluate,
    verify_permutation,
)


def row(*, found: int, complete: int, k: int = 5, lang: str = "ko") -> dict:
    return {
        "catalog_size": 100,
        "task_id": "dev-1",
        "language": lang,
        "k": k,
        "required_route_count": 1,
        "found_required_count": found,
        "full_coverage": complete,
        "candidate_json_bytes": 100,
    }


def test_strict_candidate_permutation_never_manufactures_authority() -> None:
    original = ["read.file", "export.table", "update.item"]
    assert verify_permutation(original, original[::-1]) == original[::-1]
    for illegal in (
        ["read.file", "export.table", "update.admin"],
        ["read.file", "read.file", "update.item"],
        ["read.file"],
        ["read.file", "export.table", 0],
        "read.file",
        None,
    ):
        with pytest.raises(ValueError):
            verify_permutation(original, illegal)


def test_keep_requires_actual_quality_gain_and_nonregression() -> None:
    baseline = [row(found=0, complete=0)]
    improved = [row(found=1, complete=1)]
    keep = decide(baseline, improved, candidate_p95_ms=0.1)
    assert keep["decision"] == "KEEP_RESEARCH_CANDIDATE"
    assert keep["top5_required_route_gain"] == 1
    assert keep["can_merge_product_code"] is False
    assert keep["independent_qualification"] is False
    neutral = decide(improved, copy.deepcopy(improved), candidate_p95_ms=0.1)
    assert neutral["decision"] == "DISCARD_OR_REVISE"


def test_regression_and_latency_over_budget_cannot_keep() -> None:
    a = [row(found=1, complete=1, lang="ko"),
         row(found=0, complete=0, lang="ja")]
    b = [row(found=0, complete=0, lang="ko"),
         row(found=1, complete=1, lang="ja")]
    result = decide(a, b, candidate_p95_ms=0.5)
    assert result["decision"] == "DISCARD_OR_REVISE"
    assert len(result["regressions"]) == 1
    assert result["regressions"][0]["language"] == "ko"
    with pytest.raises(ValueError):
        decide(a, b[::-1], candidate_p95_ms=0.5)
    with pytest.raises(ValueError):
        decide(a, b, candidate_p95_ms=math.nan)
    slow = decide([row(found=0, complete=0)],
                  [row(found=1, complete=1)], candidate_p95_ms=25)
    assert slow["decision"] == "DISCARD_OR_REVISE"
    assert slow["guard_results"]["candidate_ipc_p95_below_20_ms"] is False


def test_oversized_candidate_contract_bytes_rejected() -> None:
    old = [row(found=0, complete=0)]
    new = [row(found=1, complete=1)]
    new[0]["candidate_json_bytes"] = 150
    result = decide(old, new, candidate_p95_ms=1)
    assert result["decision"] == "DISCARD_OR_REVISE"
    assert result["guard_results"][
        "candidate_payload_bytes_within_110_percent_baseline"
    ] is False


def test_candidate_worker_uses_only_given_public_candidate_ids() -> None:
    with CandidateWorker() as worker:
        docs = [
            {"route_id": "read.items", "score": 1.0},
            {"route_id": "edit.items", "score": 0.5},
        ]
        result, elapsed = worker.rank("list items", docs)
        assert result == ["read.items", "edit.items"]
        assert elapsed >= 0


def test_synthetic_candidate_metadata_only_exposes_registered_public_fields() -> None:
    class Field:
        name = "result"
        semantic_id = "out.result"
        description = "result field"
        unit = None

    class Candidate:
        route_id = "demo.read"
        tool = "demo"
        endpoint = "read"
        score = 2.0
        tool_description = "Demo service"
        endpoint_description = "Read a record"
        matched_fields = ["out.result"]
        output_fields = [Field()]
        read_only = True
        destructive = False

    view, = candidate_view([Candidate()])
    assert view["route_id"] == "demo.read"
    assert view["output_fields"][0]["semantic_id"] == "out.result"
    assert "gold" not in view
    assert "authorized" not in view
    assert "principal" not in view
    assert "task_id" not in view


def test_real_current_planner_executes_proposal_baseline_pair_on_dev() -> None:
    report = evaluate(sizes=(100,), cases_per_group=1)
    assert report["id"] == "schemarouter-autoresearch-ranking-sandbox-v1"
    assert report["evaluated_requests"] == 48
    assert report["candidate_pool_k"] == 24
    assert type(report["decision"]["top5_required_route_gain"]) is int
    assert report["decision"]["decision"] in (
        "KEEP_RESEARCH_CANDIDATE", "DISCARD_OR_REVISE",
    )
    assert report["research_scope"]["actual_agent_task_success"] is False
    assert report["research_scope"]["authorization_or_execution_tested"] is False
    assert report["research_scope"]["independent_confirmation"] is False
    assert report["research_scope"]["autonomous_code_generation"] is False
    assert report["research_scope"]["may_promote"] is False
    assert report["research_scope"]["may_release"] is False
    assert len(report["case_pairs"]) == 48 * 3
    for pair in report["case_pairs"]:
        baseline = pair["baseline"]
        proposed = pair["candidate"]
        for key in ("catalog_size", "task_id", "language", "k", "required_route_count"):
            assert baseline[key] == proposed[key]
        assert len(proposed["selected_route_ids"]) <= proposed["k"]
        assert len(proposed["selected_route_ids"]) == len(
            set(proposed["selected_route_ids"])
        )
        assert proposed["found_required_count"] <= proposed["required_route_count"]


@pytest.mark.parametrize("sizes, count", [
    ((), 1),
    ((100, 100), 1),
    ((250, 100), 1),
    ((50,), 1),
    ((100,), 0),
    ((100,), 6),
    ((100,), True),
])
def test_unreviewed_case_or_catalog_scope_rejected(
    sizes: tuple[int, ...], count: int,
) -> None:
    with pytest.raises(ValueError):
        evaluate(sizes=sizes, cases_per_group=count)

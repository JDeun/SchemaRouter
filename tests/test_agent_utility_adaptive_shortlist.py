from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_agent_utility_v5_adaptive_shortlist.py"
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-adaptive-shortlist-preregistration.json"
)

spec = importlib.util.spec_from_file_location("adaptive_eval", SCRIPT)
assert spec is not None and spec.loader is not None
adaptive_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive_eval)


def _prereg() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def _ranking(scores: list[float]) -> list[dict[str, object]]:
    return [
        {
            "route_id": f"tool.route_{index}",
            "score": score,
            "schema_tokens": 10 + index,
        }
        for index, score in enumerate(scores, start=1)
    ]


def _row(
    *,
    task_id: str,
    stratum: str,
    required: list[str],
    scores: list[float],
    catalog_size: int = 100,
) -> dict:
    return {
        "task_id": task_id,
        "query": f"query for {task_id}",
        "task_stratum": stratum,
        "language": "en",
        "catalog_size": catalog_size,
        "required_route_ids": required,
        "retrieval_latency_ms": 12.5,
        "ranking": _ranking(scores),
        "prefix_schema_tokens": {
            str(depth): depth * 25
            for depth in range(1, 11)
        },
    }


def test_adaptive_depth_is_positive_affine_invariant() -> None:
    prereg = _prereg()
    policy = next(
        item
        for item in prereg["candidate_policies"]["adaptive"]
        if item["id"] == "REL-GAP-010"
    )
    positions = prereg["score_semantics"]["evaluated_positions"]
    scores = [1.0, 0.95, 0.9, 0.5, 0.49, 0.48, 0.47, 0.46, 0.45, 0.44]

    original = adaptive_eval._adaptive_k(scores, policy, positions)
    transformed = adaptive_eval._adaptive_k(
        [3.0 * score + 7.0 for score in scores],
        policy,
        positions,
    )

    assert original == transformed == 3


def test_zero_score_spread_fails_open_to_max_k() -> None:
    prereg = _prereg()
    policy = prereg["candidate_policies"]["adaptive"][0]
    positions = prereg["score_semantics"]["evaluated_positions"]

    assert adaptive_eval._adaptive_k(
        [0.5] * 10,
        policy,
        positions,
    ) == 10


def test_bits_over_random_uses_hypergeometric_any_hit_baseline() -> None:
    probability = adaptive_eval._random_any_required_probability(
        catalog_size=100,
        required_count=1,
        k=5,
    )
    assert math.isclose(probability, 0.05, rel_tol=0.0, abs_tol=1e-12)

    bor = adaptive_eval._bits_over_random(
        observed_any_required=1.0,
        random_any_required=probability,
    )
    assert bor is not None
    assert 4.32 < bor < 4.33


def test_unsupported_rows_do_not_inflate_supported_coverage() -> None:
    prereg = _prereg()
    scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    rows = [
        _row(
            task_id="supported",
            stratum="clear_single_tool",
            required=["tool.route_1"],
            scores=scores,
        ),
        _row(
            task_id="unsupported",
            stratum="near_domain_unsupported",
            required=[],
            scores=scores,
        ),
    ]

    result = adaptive_eval.evaluate(
        rows,
        prereg,
        strict_surface=False,
    )
    fixed3 = result["policy_metrics"]["FIXED-3"]

    assert fixed3["supported_required_route_recall"] == 1.0
    assert fixed3["supported_all_required_full_coverage"] == 1.0
    assert fixed3["candidate_count"]["count"] == 2
    assert fixed3["unsupported_candidate_count"][
        "near_domain_unsupported"
    ]["count"] == 1


def test_validator_rejects_gold_routes_on_unsupported_rows() -> None:
    prereg = _prereg()
    scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    row = _row(
        task_id="bad-unsupported",
        stratum="out_of_domain",
        required=["tool.route_1"],
        scores=scores,
    )

    try:
        adaptive_eval.evaluate(
            [row],
            prereg,
            strict_surface=False,
        )
    except ValueError as exc:
        assert "unsupported row" in str(exc)
    else:
        raise AssertionError("unsupported gold-route leakage was not rejected")


def test_adaptive_dev_authoring_plan_freezes_slots_without_content() -> None:
    generator_path = (
        ROOT
        / "scripts"
        / "generate_agent_utility_v5_adaptive_dev_authoring_plan.py"
    )
    generator_spec = importlib.util.spec_from_file_location(
        "adaptive_plan",
        generator_path,
    )
    assert generator_spec is not None and generator_spec.loader is not None
    generator = importlib.util.module_from_spec(generator_spec)
    generator_spec.loader.exec_module(generator)

    plan = generator.build_authoring_plan()

    assert plan["semantic_task_count"] == 240
    assert plan["cell_count"] == 48
    assert plan["tasks_per_cell"] == 5
    assert plan["slots_sha256"] == (
        "5c3eb9608cfad8b73733f89c83dbfb22"
        "abf0892076d9f5acf933a296f5c157df"
    )
    assert plan["b1_rows_used"] is False
    assert plan["b2_rows_used"] is False
    assert all(
        not set(slot).intersection(generator.FORBIDDEN_CONTENT_KEYS)
        for slot in plan["slots"]
    )


def test_adaptive_eligibility_reads_machine_preregistered_gates() -> None:
    prereg = _prereg()
    gates = prereg["dev_selection"]["eligibility_thresholds"]
    assert gates == {
        "required_tool_set_recall_min": 0.97,
        "all_required_full_coverage_min": 0.97,
        "mean_candidate_count_max_exclusive": 5.0,
        "p95_candidate_count_max": 10,
        "mean_schema_tokens_must_be_less_than_fixed5": True,
    }

    metrics = {
        "supported_required_route_recall": 0.98,
        "supported_all_required_full_coverage": 0.98,
        "candidate_count": {"mean": 4.0, "p95": 8.0},
        "schema_tokens": {"mean": 80.0},
    }
    fixed5 = {"schema_tokens": {"mean": 100.0}}
    assert adaptive_eval._adaptive_eligible(
        metrics,
        fixed5,
        prereg,
    )

    prereg["dev_selection"]["eligibility_thresholds"][
        "required_tool_set_recall_min"
    ] = 0.99
    assert not adaptive_eval._adaptive_eligible(
        metrics,
        fixed5,
        prereg,
    )


def test_prefix_tool_tokens_are_used_instead_of_candidate_additivity() -> None:
    prereg = _prereg()
    scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    row = _row(
        task_id="token-accounting",
        stratum="clear_single_tool",
        required=["tool.route_1"],
        scores=scores,
    )
    row["prefix_schema_tokens"]["3"] = 91

    result = adaptive_eval.evaluate(
        [row],
        prereg,
        strict_surface=False,
    )

    assert result["policy_metrics"]["FIXED-3"]["schema_tokens"]["mean"] == 91


def test_worst_catalog_coverage_prevents_pooled_masking() -> None:
    prereg = _prereg()
    scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    rows = [
        _row(
            task_id="catalog-robustness",
            stratum="clear_single_tool",
            required=["tool.route_1"],
            scores=scores,
            catalog_size=size,
        )
        for size in (100, 250, 500)
    ]
    ranking = rows[-1]["ranking"]
    route_ids = [
        candidate["route_id"]
        for candidate in ranking
    ]
    shifted_route_ids = [*route_ids[1:], route_ids[0]]
    for candidate, route_id in zip(
        ranking,
        shifted_route_ids,
        strict=True,
    ):
        candidate["route_id"] = route_id

    result = adaptive_eval.evaluate(
        rows,
        prereg,
        strict_surface=False,
    )
    fixed3 = result["policy_metrics"]["FIXED-3"]

    assert fixed3["supported_required_route_recall"] == 2 / 3
    assert fixed3["worst_catalog_required_route_recall"] == 0.0
    assert fixed3["per_catalog"]["100"][
        "supported_required_route_recall"
    ] == 1.0
    assert fixed3["per_catalog"]["250"][
        "supported_required_route_recall"
    ] == 1.0
    assert fixed3["per_catalog"]["500"][
        "supported_required_route_recall"
    ] == 0.0

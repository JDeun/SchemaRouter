from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose_agent_utility_v5_retrieval.py"

spec = importlib.util.spec_from_file_location("adaptive_diagnose", SCRIPT)
assert spec is not None and spec.loader is not None
diagnose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnose)


def _ranking(scores: list[tuple[str, float]]) -> list[dict[str, object]]:
    return [
        {"route_id": route_id, "score": score}
        for route_id, score in scores
    ]


def test_diagnosis_marks_cutoff_tie_collision() -> None:
    ranking = _ranking(
        [
            *[(f"route-{index}", 10.0) for index in range(1, 12)],
            ("gold", 10.0),
        ]
    )

    result = diagnose._classify_required_route(
        full_ranking=ranking,
        route_id="gold",
    )

    assert result["rank"] == 12
    assert result["miss_class"] == "tie_collision"
    assert result["equal_score_candidate_count"] == 12
    assert result["strictly_higher_score_candidate_count"] == 0


def test_diagnosis_marks_true_below_cutoff_miss() -> None:
    ranking = _ranking(
        [
            *[(f"route-{index}", 10.0) for index in range(1, 11)],
            ("gold", 5.0),
        ]
    )

    result = diagnose._classify_required_route(
        full_ranking=ranking,
        route_id="gold",
    )

    assert result["rank"] == 11
    assert result["miss_class"] == "below_cutoff"
    assert result["cutoff_score"] == 10.0


def test_diagnosis_marks_zero_score_miss() -> None:
    ranking = _ranking(
        [
            *[(f"route-{index}", 2.0) for index in range(1, 11)],
            ("gold", 0.0),
        ]
    )

    result = diagnose._classify_required_route(
        full_ranking=ranking,
        route_id="gold",
    )

    assert result["miss_class"] == "zero_score"


def test_diagnosis_marks_covered_route() -> None:
    ranking = _ranking(
        [
            ("gold", 4.0),
            *[(f"route-{index}", 3.0) for index in range(1, 11)],
        ]
    )

    result = diagnose._classify_required_route(
        full_ranking=ranking,
        route_id="gold",
    )

    assert result["rank"] == 1
    assert result["miss_class"] == "covered"

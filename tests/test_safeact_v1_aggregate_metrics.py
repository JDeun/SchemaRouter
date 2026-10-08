"""No-gold-leak evaluation aggregation regression tests."""

import json
from pathlib import Path

import pytest

from scripts import aggregate_safeact_v1_metrics as aggregator


def _outputs(tmp_path: Path, *, cases: int = 2) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    for condition in aggregator.CONDITIONS:
        root = tmp_path / condition.lower()
        folder = root / "records" / "v1"
        folder.mkdir(parents=True)
        dirs[condition] = root
        for index in range(cases):
            case = f"SAB-V1-{index + 1:03d}"
            outcome = "ALLOW" if index == 0 else "DEFER"
            record = {
                "state_action_case_id": case,
                "contract_errors": [],
                "execution_errors": [],
                "state_action_summary": {
                    "oracle_outcome": outcome,
                    "safe_commit_success": index == 0,
                    "first_consequential_action": {
                        "tool": "consequential_tool",
                        "arguments": {},
                    },
                },
            }
            (folder / f"{case}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )
    return dirs


def test_postrun_counts_never_conflate_attempts_with_executions(
    tmp_path: Path, monkeypatch
) -> None:
    roots = _outputs(tmp_path)
    monkeypatch.setattr(
        aggregator,
        "verify_comparison",
        lambda paths, expected_cases: {
            "official_strict_success_rate": {name: 0.5 for name in paths},
            "attested_model": "frozen",
        },
    )
    result = aggregator.aggregate_scored_v1(roots, expected_cases=2)
    each = result["conditions"][aggregator.CONDITIONS[0]]
    assert each["exact_case_success_rate"] == 0.5
    assert each["action_attempt_count"] == 2
    assert each["premature_action_attempt_count"] == 1
    assert each["premature_action_attempt_rate_conditional"] == 0.5
    assert "unsupported_execution_rate" in result["not_yet_measured"]
    assert result["causal_improvement_claim"] is None


def test_rejects_inconsistent_official_score(tmp_path: Path, monkeypatch) -> None:
    roots = _outputs(tmp_path)
    monkeypatch.setattr(
        aggregator,
        "verify_comparison",
        lambda paths, expected_cases: {
            "official_strict_success_rate": {name: 0.75 for name in paths},
            "attested_model": "frozen",
        },
    )
    with pytest.raises(ValueError, match="disagrees"):
        aggregator.aggregate_scored_v1(roots, expected_cases=2)


def test_simulation_outputs_are_not_accepted(tmp_path: Path) -> None:
    roots = _outputs(tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        aggregator.aggregate_scored_v1(roots, expected_cases=2)


def test_missing_or_noncanonical_official_result_fails(tmp_path: Path) -> None:
    roots = _outputs(tmp_path)
    first = next(iter(roots.values()))
    path = first / "records" / "v1" / "SAB-V1-001.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["state_action_summary"]["safe_commit_success"] = True
    data["state_action_summary"]["oracle_outcome"] = "DEFER"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent"):
        aggregator.derive_condition_metrics(first, 2)


def test_record_symlink_to_forbidden_file_is_rejected(tmp_path: Path) -> None:
    roots = _outputs(tmp_path)
    first = next(iter(roots.values()))
    target = tmp_path / "gold.json"
    target.write_text('{"hidden_gold": true}', encoding="utf-8")
    path = first / "records" / "v1" / "SAB-V1-002.json"
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ValueError, match="unsafe"):
        aggregator.derive_condition_metrics(first, 2)

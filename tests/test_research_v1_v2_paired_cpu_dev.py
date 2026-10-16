"""Audited historical incumbent identity and paired current retrieved DEV guard."""
from __future__ import annotations

import json

import pytest

from scripts import research_v1_v2_paired_cpu_dev as comparison
from scripts.research_actions_width_search_dev import validated_genome


def test_v1_v2_are_actual_frozen_distinct_actions_artifacts() -> None:
    v1, v2, src = comparison.frozen_genomes()
    assert v1["width"] == 24
    assert v2["width"] == 64
    assert src["v1"]["run_id"] == 38828196450
    assert src["v2"]["run_id"] == 38828191428
    assert src["v1"]["epoch"] == 12 and src["v1"]["trials"] == 275
    assert v1 != v2
    assert validated_genome(v1) == v1
    assert validated_genome(v2) == v2
    assert src["restrictions"]["may_promote"] is False


def test_manifest_gold_or_champion_tampering_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    manifest = json.loads(comparison.MANIFEST.read_text(encoding="utf-8"))
    for field, invalid in (
        ("source_corpus_sha256", "0" * 64),
        ("schema_version", 2),
        ("restrictions", {"may_promote": True}),
    ):
        altered = json.loads(json.dumps(manifest))
        altered[field] = invalid
        filename = tmp_path / "mutated.json"
        filename.write_text(json.dumps(altered), encoding="utf-8")
        monkeypatch.setattr(comparison, "MANIFEST", filename)
        with pytest.raises(ValueError):
            comparison.frozen_genomes()


def test_no_wrong_cross_cohort_pairing_or_malformed_case_budget() -> None:
    a = {
        "task_id": "en-a", "catalog_size": 100, "language": "en",
        "k": 5, "required_route_count": 1, "found_required_count": 1,
        "full_coverage": 1, "candidate_json_bytes": 100,
    }
    b = dict(a, task_id="ko-b")
    with pytest.raises(ValueError):
        comparison.compare_pairs([a], [b])
    for wrong in (0, 6, -1, True):
        with pytest.raises(ValueError):
            comparison.assess(cases_per_group=wrong)


def test_actual_current_planner_paired_frozen_incumbents() -> None:
    report = comparison.assess(cases_per_group=1)
    assert report["id"] == "frozen_V1_V2_exact_current_CPU_paired_DEV"
    assert report["paired_real_planner_calls"] == 3 * 48 * 3
    assert report["evaluated_requests_per_candidate"] == 3 * 48
    assert len(report["paired_results"]["cohorts"]) == 3 * 6 * 3
    assert report["incumbent_v1"]["width"] == 24
    assert report["challenger_v2"]["width"] == 64
    assert report["scope"]["retrospective_comparison_of_tuned_candidates"] is True
    assert report["scope"]["uses_new_independent_holdout"] is False
    assert report["is_external_independent_confirmation"] is False
    assert report["is_eligible_for_product_promotion"] is False
    assert report["existing_strict_dev_guard"]["can_merge_product_code"] is False
    assert report["paired_results"]["v1_top5"]["supported_cases"] > 0
    assert report["paired_results"]["v2_top5"]["supported_cases"] > 0

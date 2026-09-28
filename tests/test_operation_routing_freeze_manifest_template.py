from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "benchmarks" / "operation-routing-freeze-manifest.template.json"


def _load() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def test_freeze_manifest_locks_standing_target() -> None:
    data = _load()
    target = data["production_target"]

    assert target["supported_exact_route_accuracy_min"] == 0.85
    assert target["near_domain_unsupported_rejection_min"] == 0.97
    assert target["out_of_domain_rejection"] == 1.0
    assert target["false_route_rate_max"] == 0.01
    assert target["authority_violations_max"] == 0
    assert target["execution_errors_max"] == 0
    assert target["combined_p95_ms_max"] == 250.0


def test_freeze_manifest_preserves_authority_invariants() -> None:
    data = _load()
    authority = data["candidate"]["authority"]

    assert authority["finite_registered_ids_only"] is True
    assert authority["rank2_fallback"] is False
    assert authority["pseudo_route"] is False
    assert authority["provider_can_create_execution_authority"] is False


def test_freeze_manifest_requires_dev_and_fresh_provenance_slots() -> None:
    data = _load()

    for phase in ("development", "fresh_confirmation"):
        evidence = data["evidence"][phase]
        assert "corpus_sha256" in evidence
        assert "workflow_run_id" in evidence
        assert "artifact_id" in evidence
        assert "artifact_sha256" in evidence
        assert "metrics" in evidence

    fresh = data["evidence"]["fresh_confirmation"]
    assert "surface_id" in fresh
    assert "zero_overlap_audit_artifact" in fresh


def test_freeze_manifest_keeps_consumed_fresh_sets_out_of_tuning() -> None:
    data = _load()
    governance = data["governance"]

    assert governance["failed_confirmation_tuning_forbidden"] == [270, 287]
    assert governance["semantic_retuning_after_freeze_allowed"] is False
    assert governance["calibration_or_blind_inspected"] is False
    assert governance["calibration_issue"] == 198
    assert governance["paper_evidence_issue"] == 199
    assert governance["canonical_tracker_issue"] == 200

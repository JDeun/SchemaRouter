from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_operation_routing_freeze_manifest.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "validate_operation_routing_freeze_manifest",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load freeze manifest validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics() -> dict:
    return {
        "supported_exact_route_accuracy": 0.86,
        "near_domain_unsupported_rejection": 0.98,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.009,
        "authority_violations": 0,
        "execution_errors": 0,
        "combined_p95_ms": 200.0,
    }


def _manifest() -> dict:
    digest = "a" * 64
    revision = "b" * 40
    return {
        "schema_version": 1,
        "kind": "operation-routing-freeze-manifest",
        "status": "frozen-dev",
        "production_target": {
            "supported_exact_route_accuracy_min": 0.85,
            "near_domain_unsupported_rejection_min": 0.97,
            "out_of_domain_rejection": 1.0,
            "false_route_rate_max": 0.01,
            "authority_violations_max": 0,
            "execution_errors_max": 0,
            "combined_p95_ms_max": 250.0,
        },
        "candidate": {
            "candidate_id": "candidate-v1",
            "source_revision": revision,
            "architecture_id": "bge-plus-external-veto",
            "authority": {
                "route_authority": "BGE raw registered top-1",
                "verifier_role": "veto-only",
                "finite_registered_ids_only": True,
                "rank2_fallback": False,
                "pseudo_route": False,
                "provider_can_create_execution_authority": False,
            },
            "models": [
                {
                    "role": "ranker",
                    "name": "BAAI/bge-m3",
                    "revision": revision,
                }
            ],
            "runtime": {
                "python": "3.12",
                "dependency_versions": {"sentence-transformers": "5.0.0"},
                "hardware_label": "github-ubuntu-cpu",
                "optimization": None,
            },
            "representation": {
                "query_representation_sha256": digest,
                "capability_representation_sha256": digest,
                "prompt_or_instruction_sha256": digest,
                "option_ordering_rule": "lexical registered route ID",
            },
            "decision_rule": {
                "rule_id": "p0.95",
                "threshold": 0.95,
                "parameters": {},
            },
        },
        "evidence": {
            "development": {
                "corpus_seed": "dev-seed",
                "corpus_sha256": digest,
                "workflow_run_id": 123,
                "artifact_id": 456,
                "artifact_sha256": digest,
                "metrics": _metrics(),
            },
            "fresh_confirmation": {
                "surface_id": None,
                "corpus_seed": None,
                "corpus_sha256": None,
                "zero_overlap_audit_artifact": None,
                "workflow_run_id": None,
                "artifact_id": None,
                "artifact_sha256": None,
                "metrics": None,
            },
        },
        "governance": {
            "failed_confirmation_tuning_forbidden": [270, 287],
            "semantic_retuning_after_freeze_allowed": False,
            "runtime_only_optimization_after_quality_pass_requires_same_semantics": True,
            "calibration_or_blind_inspected": False,
            "calibration_issue": 198,
            "paper_evidence_issue": 199,
            "canonical_tracker_issue": 200,
        },
        "created_at_utc": "2026-09-28T03:30:00Z",
        "notes": None,
    }


def test_validator_accepts_complete_dev_freeze() -> None:
    module = _module()
    module.validate_manifest(_manifest(), phase="dev")


def test_validator_accepts_fresh_confirmed_manifest() -> None:
    module = _module()
    manifest = _manifest()
    manifest["status"] = "fresh-confirmed"
    fresh = manifest["evidence"]["fresh_confirmation"]
    fresh.update(
        {
            "surface_id": "confirmation-v1",
            "corpus_seed": "fresh-seed",
            "corpus_sha256": "c" * 64,
            "zero_overlap_audit_artifact": "audit.json",
            "workflow_run_id": 789,
            "artifact_id": 101112,
            "artifact_sha256": "d" * 64,
            "metrics": _metrics(),
        }
    )
    module.validate_manifest(manifest, phase="fresh")


def test_validator_rejects_target_drift() -> None:
    module = _module()
    manifest = _manifest()
    manifest["production_target"]["false_route_rate_max"] = 0.02

    with pytest.raises(module.FreezeManifestError, match="production_target"):
        module.validate_manifest(manifest, phase="dev")


def test_validator_rejects_authority_drift() -> None:
    module = _module()
    manifest = _manifest()
    manifest["candidate"]["authority"]["rank2_fallback"] = True

    with pytest.raises(module.FreezeManifestError, match="rank2_fallback"):
        module.validate_manifest(manifest, phase="dev")


def test_validator_rejects_failed_dev_metrics() -> None:
    module = _module()
    manifest = _manifest()
    manifest["evidence"]["development"]["metrics"]["supported_exact_route_accuracy"] = 0.84

    with pytest.raises(module.FreezeManifestError, match="exact-route"):
        module.validate_manifest(manifest, phase="dev")


def test_validator_requires_fresh_provenance_for_fresh_phase() -> None:
    module = _module()
    manifest = deepcopy(_manifest())
    manifest["status"] = "fresh-confirmed"

    with pytest.raises(module.FreezeManifestError):
        module.validate_manifest(manifest, phase="fresh")


def test_validator_accepts_provider_model_version_and_prefixed_artifact_digest() -> None:
    module = _module()
    manifest = _manifest()
    manifest["candidate"]["models"][0]["revision"] = "provider-snapshot-2026-09-28"
    manifest["evidence"]["development"]["artifact_sha256"] = "sha256:" + "e" * 64

    module.validate_manifest(manifest, phase="dev")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("supported_exact_route_accuracy", 1.1),
        ("near_domain_unsupported_rejection", -0.1),
        ("out_of_domain_rejection", 1.1),
        ("false_route_rate", -0.01),
        ("combined_p95_ms", -1.0),
    ],
)
def test_validator_rejects_impossible_metric_ranges(
    key: str,
    value: float,
) -> None:
    module = _module()
    manifest = _manifest()
    manifest["evidence"]["development"]["metrics"][key] = value

    with pytest.raises(module.FreezeManifestError):
        module.validate_manifest(manifest, phase="dev")

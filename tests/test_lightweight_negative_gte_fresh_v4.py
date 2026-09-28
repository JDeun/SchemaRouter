from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_fresh_surface_is_distinct_and_balanced() -> None:
    module = _load(
        "fresh_surface",
        "scripts/generate_decision_routing_quality_v4_lightweight_confirmation.py",
    )
    cases, metadata = module.build_confirmation()

    assert len(cases) == 1800
    assert metadata["surface_version"] == (
        "lightweight-bge-gte-operational-envelope-v1"
    )
    assert metadata["normalized_exact_overlap_with_reference_dev"] == 0
    assert all(
        value == 0
        for value in metadata[
            "normalized_exact_overlap_with_prior_fresh_surfaces"
        ].values()
    )
    assert all(metadata["prior_surface_regeneration_verified"].values())
    assert metadata["tuning_eligible"] is False
    assert metadata["calibration_or_blind"] is False


def test_fresh_gate_uses_quality_and_runtime_not_dev_parity() -> None:
    module = _load(
        "fresh_eval",
        "scripts/evaluate_lightweight_negative_gte_fresh_v4.py",
    )
    manifest = {
        "gate": {
            "supported_exact_route_accuracy_min": 0.85,
            "near_domain_unsupported_rejection_min": 0.97,
            "out_of_domain_rejection": 1.0,
            "false_route_rate_max": 0.01,
            "authority_violations_max": 0,
            "execution_errors_max": 0,
            "p95_ms_max": 250.0,
        }
    }
    summary = {
        "supported_exact_route_accuracy": 0.86,
        "near_domain_unsupported_rejection": 0.98,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.009,
        "authority_violations": 0,
        "execution_errors": 0,
        "parity_mismatch_count": 999,
        "parity_counts_match": False,
        "total_latency_ms": {"p95": 200.0},
    }

    assert module._fresh_gate(summary, manifest) is True


def test_fresh_gate_rejects_quality_or_runtime_failure() -> None:
    module = _load(
        "fresh_eval_failure",
        "scripts/evaluate_lightweight_negative_gte_fresh_v4.py",
    )
    manifest = {
        "gate": {
            "supported_exact_route_accuracy_min": 0.85,
            "near_domain_unsupported_rejection_min": 0.97,
            "out_of_domain_rejection": 1.0,
            "false_route_rate_max": 0.01,
            "authority_violations_max": 0,
            "execution_errors_max": 0,
            "p95_ms_max": 250.0,
        }
    }
    summary = {
        "supported_exact_route_accuracy": 0.84,
        "near_domain_unsupported_rejection": 0.98,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.009,
        "authority_violations": 0,
        "execution_errors": 0,
        "total_latency_ms": {"p95": 200.0},
    }
    assert module._fresh_gate(summary, manifest) is False

    summary["supported_exact_route_accuracy"] = 0.86
    summary["total_latency_ms"]["p95"] = 251.0
    assert module._fresh_gate(summary, manifest) is False


def test_new_surface_adds_split_marker_without_changing_prior_payloads() -> None:
    module = _load(
        "fresh_surface_split_contract",
        "scripts/generate_decision_routing_quality_v4_lightweight_confirmation.py",
    )
    cases, metadata = module.build_confirmation()

    assert all(case.get("split") == "fresh_confirmation" for case in cases)
    assert metadata["prior_surface_regeneration_verified"] == {
        "zero-false-confirmation-wrappers-v1": True,
        "learned-verifier-confirmation-wrappers-v1": True,
    }

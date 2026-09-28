from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module(path: str, name: str):
    script = ROOT / path
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_selection_matches_successful_oof_rule() -> None:
    analysis = _module(
        "scripts/analyze_oof_learned_verifier_v4.py",
        "analyze_oof_learned_verifier_v4_contract",
    )
    path = ROOT / "benchmarks" / (
        "operation-routing-v4-frozen-learned-verifier.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    selected = data["selected_rule"]
    assert selected["classifier"] == "HistGradientBoostingClassifier"
    assert selected["acceptance_threshold"] == 0.50
    assert selected["scikit_learn"] == "1.7.2"
    assert selected["acceptance_threshold"] in analysis.ACCEPTANCE_THRESHOLDS
    assert len(analysis.CONTINUOUS_FEATURES) == 19
    assert analysis.CATEGORICAL_FEATURES == ("raw_top_route",)


def test_evaluator_requires_same_model_sha(tmp_path: Path) -> None:
    pytest.importorskip("joblib")
    pytest.importorskip("sklearn")
    evaluator = _module(
        "scripts/evaluate_frozen_learned_verifier_v4.py",
        "evaluate_frozen_learned_verifier_v4",
    )
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"not-the-frozen-model")
    manifest = {
        "candidate": "frozen-hgb-winner-verifier-v1",
        "selected_classifier": "hgb",
        "selected_threshold": 0.50,
        "continuous_features": list(evaluator.CONTINUOUS_FEATURES),
        "categorical_features": list(evaluator.CATEGORICAL_FEATURES),
        "model_sha256": "0" * 64,
        "runtime": {"scikit_learn": "1.7.2"},
    }
    with pytest.raises(ValueError, match="frozen model SHA mismatch"):
        evaluator._verify_manifest(model_path, manifest)


def test_fresh_surface_contract_is_new_and_zero_overlap() -> None:
    generator = _module(
        "scripts/generate_decision_routing_quality_v4_learned_confirmation.py",
        "generate_learned_confirmation",
    )
    seed = (
        "operation-routing-quality-v4-"
        "learned-verifier-confirmation-2026-09-28-a"
    )
    reference_seed = "operation-routing-quality-v4-development-2026-09-27"
    cases, metadata = generator.build_confirmation(
        seed=seed,
        reference_seed=reference_seed,
    )
    assert len(cases) == 1800
    assert (
        metadata["surface_version"]
        == "learned-verifier-confirmation-wrappers-v1"
    )
    assert metadata["normalized_exact_overlap_with_reference_dev"] == 0
    assert metadata["distinct_from_failed_270_by_seed_and_surface_version"]
    assert metadata["failed_270_artifact_read"] is False


def test_preregistration_pins_fit_once_and_no_refit() -> None:
    path = ROOT / "benchmarks" / (
        "operation-routing-v4-frozen-learned-verifier.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["work_item"] == 287
    assert data["selected_rule"]["classifier"] == (
        "HistGradientBoostingClassifier"
    )
    assert data["selected_rule"]["acceptance_threshold"] == 0.5
    assert data["selected_rule"]["scikit_learn"] == "1.7.2"
    assert data["fit_once"]["required"] is True
    assert data["fit_once"]["refit_after_fit_stage"] is False
    assert (
        data["fit_once"]["same_serialized_file_for_all_confirmation_stages"]
        is True
    )

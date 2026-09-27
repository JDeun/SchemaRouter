from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_routing_v4_stage_diagnostics.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_routing_v4_stage_diagnostics",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load stage diagnostics analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    backend: str,
    case_id: str,
    expected: str | None,
    *,
    predicted: str | None,
    category: str,
    similarity: float,
    abstained: bool,
    top_route: str,
) -> dict:
    return {
        "backend": backend,
        "case_id": case_id,
        "category": category,
        "language": "en",
        "unsupported_family": (
            "inventory.family_1" if expected is None else None
        ),
        "expected": expected,
        "predicted": predicted,
        "correct": predicted == expected,
        "candidate_fit_invoked": True,
        "candidate_fit_surface": "capability_fit",
        "candidate_fit_top_option_id": "fit:0",
        "candidate_fit_top_route_label": top_route,
        "candidate_fit_top_similarity": similarity,
        "candidate_fit_second_similarity": similarity - 0.1,
        "candidate_fit_top_margin": 0.1,
        "candidate_fit_abstained": abstained,
        "candidate_fit_reason": (
            "below_min_similarity" if abstained else None
        ),
    }


def test_stage_diagnostics_counts_recoverable_candidate_fit_abstention() -> None:
    module = _module()
    report = {
        "rows": [
            _row(
                module.BASELINE,
                "supported",
                "inventory.update",
                predicted=None,
                category="v4_supported_natural",
                similarity=0.24,
                abstained=True,
                top_route="inventory.update",
            ),
            _row(
                module.BASELINE,
                "near",
                None,
                predicted=None,
                category="near_domain_unsupported_operation",
                similarity=0.10,
                abstained=True,
                top_route="inventory.update",
            ),
        ],
        "reproducibility": {
            "source_revision": "abc",
            "corpus_sha256": "def",
        },
    }

    result = module.analyze(report)
    candidate_fit = result["candidate_fit"]

    assert candidate_fit["supported_abstentions"] == 1
    assert (
        candidate_fit["supported_abstentions_where_top_route_was_expected"]
        == 1
    )
    assert (
        candidate_fit["supported_top_route_exact_rate_over_all_supported"]
        == 1.0
    )
    threshold = next(
        item
        for item in candidate_fit["threshold_diagnostic"]
        if item["min_similarity"] == 0.25
    )
    assert threshold["supported_gate_pass_rate"] == 0.0
    assert threshold["near_domain_gate_rejection_rate"] == 1.0

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_gte_consensus_v4.py"
MANIFEST = ROOT / "benchmarks" / "operation-routing-v4-bge-gte-consensus.json"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_gte_consensus_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load BGE/GTE consensus diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_locks_threshold_free_veto_only_rule() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["rule"]["id"] == "global_top1_consensus"
    assert data["rule"]["score_threshold"] is None
    assert data["rule"]["margin_threshold"] is None
    assert data["rule"]["route_local_thresholds"] is False
    assert data["rule"]["rank2_fallback"] is False
    assert data["rule"]["pseudo_route"] is False
    assert data["gte_consensus"]["can_change_route"] is False
    assert data["data"]["forbidden_fresh_issues"] == [270, 287, 326]


def test_gte_identity_and_fusion_are_frozen() -> None:
    module = _module()
    assert module.GTE_MODEL == "Alibaba-NLP/gte-multilingual-base"
    assert (
        module.GTE_REVISION
        == "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
    )
    assert module.GTE_SCHEMA_WEIGHT == 0.25
    assert module.GTE_ACTION_WEIGHT == 0.75


def _row(
    *,
    expected: str | None,
    bge: str,
    gte: str,
    category: str,
    language: str = "en",
    family: str | None = None,
) -> dict:
    return {
        "expected": expected,
        "bge_raw_route": bge,
        "gte_raw_route": gte,
        "consensus": bge == gte,
        "category": category,
        "language": language,
        "unsupported_family": family,
    }


def test_consensus_metrics_execute_only_same_bge_winner() -> None:
    module = _module()
    rows = [
        _row(
            expected="tool.a",
            bge="tool.a",
            gte="tool.a",
            category="v4_supported_natural",
        ),
        _row(
            expected="tool.b",
            bge="tool.b",
            gte="tool.a",
            category="v4_supported_natural",
        ),
        _row(
            expected=None,
            bge="tool.a",
            gte="tool.b",
            category="near_domain_unsupported_operation",
            family="unsupported-x",
        ),
        _row(
            expected=None,
            bge="tool.a",
            gte="tool.a",
            category="out_of_domain",
        ),
    ]

    metrics = module._metrics(rows)

    assert metrics["supported_correct"] == 1
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 0.0
    assert metrics["false_routes"] == 1
    assert metrics["false_route_rate"] == 0.5


def test_quality_gate_is_exact_85_97_100_1() -> None:
    module = _module()
    passing = {
        "supported_exact_route_accuracy": 0.85,
        "near_domain_unsupported_rejection": 0.97,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.01,
    }
    assert module._quality_pass(passing, errors=0, authority=0)

    failed = dict(passing)
    failed["false_route_rate"] = 0.0101
    assert not module._quality_pass(failed, errors=0, authority=0)

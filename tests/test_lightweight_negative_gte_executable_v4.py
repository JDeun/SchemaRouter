from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_lightweight_negative_gte_executable_v4.py"
MANIFEST = (
    ROOT
    / "benchmarks"
    / "operation-routing-v4-lightweight-negative-gte-executable.json"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_lightweight_negative_gte_executable_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load executable candidate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_negative_veto_is_exact_frozen_conjunction() -> None:
    module = _module()
    assert module._negative_veto(
        max_negative_score=0.55,
        negative_advantage=0.05,
        score_min=0.55,
        advantage_min=0.05,
    )
    assert not module._negative_veto(
        max_negative_score=0.549999,
        negative_advantage=0.05,
        score_min=0.55,
        advantage_min=0.05,
    )
    assert not module._negative_veto(
        max_negative_score=0.60,
        negative_advantage=0.049999,
        score_min=0.55,
        advantage_min=0.05,
    )


def test_gte_rescue_requires_same_bge_winner() -> None:
    module = _module()
    rule = {
        "min_gte_score": 0.5,
        "min_gte_margin": 0.02,
        "max_base_score_deficit": 0.05,
        "max_base_margin_deficit": 0.0,
    }
    assert module._gte_rescue(
        gte_route="calendar.create",
        bge_route="calendar.create",
        gte_score=0.6,
        gte_margin=0.03,
        base_score_deficit=0.01,
        base_margin_deficit=0.0,
        rule=rule,
    )
    assert not module._gte_rescue(
        gte_route="calendar.list",
        bge_route="calendar.create",
        gte_score=0.9,
        gte_margin=0.5,
        base_score_deficit=0.0,
        base_margin_deficit=0.0,
        rule=rule,
    )


def test_gte_rescue_obeys_all_frozen_boundaries() -> None:
    module = _module()
    rule = {
        "min_gte_score": 0.5,
        "min_gte_margin": 0.02,
        "max_base_score_deficit": 0.05,
        "max_base_margin_deficit": 0.01,
    }
    common = {
        "gte_route": "tool.a",
        "bge_route": "tool.a",
        "gte_score": 0.6,
        "gte_margin": 0.03,
        "base_score_deficit": 0.04,
        "base_margin_deficit": 0.01,
        "rule": rule,
    }
    assert module._gte_rescue(**common)

    for key, value in (
        ("gte_score", 0.49),
        ("gte_margin", 0.019),
        ("base_score_deficit", 0.051),
        ("base_margin_deficit", 0.011),
    ):
        changed = dict(common)
        changed[key] = value
        assert not module._gte_rescue(**changed)


def test_manifest_freezes_expected_models_and_rules() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["bge"]["revision"] == (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )
    assert data["gte"]["revision"] == (
        "087a024525fd6e2fe749cb4679d218d8bcc95bdd"
    )
    assert data["negative_veto"]["max_negative_score_min"] == 0.55
    assert data["negative_veto"]["negative_advantage_min"] == 0.05
    assert len(data["gte"]["rules"]) == 16
    assert data["expected_parity"]["supported_correct"] == 980
    assert data["expected_parity"]["false_routes"] == 4
    assert data["gate"]["p95_ms_max"] == 250.0


def test_reference_rows_requires_complete_unique_case_set(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "reference.json"
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {"case_id": f"case-{index}", "final_route": None}
                    for index in range(1800)
                ]
            }
        ),
        encoding="utf-8",
    )
    indexed = module._reference_rows(path)
    assert len(indexed) == 1800

    data = json.loads(path.read_text(encoding="utf-8"))
    data["rows"][1]["case_id"] = data["rows"][0]["case_id"]
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        module._reference_rows(path)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate reference case ID must fail")

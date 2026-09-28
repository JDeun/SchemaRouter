from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_alias_envelope_v4.py"
MANIFEST = ROOT / "benchmarks" / "operation-routing-v4-bge-alias-envelope.json"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_alias_envelope_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load alias-envelope diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_forbids_dev_fitted_and_fresh_calibration() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["registry_calibration"]["labeled_dev_rows_used"] is False
    assert data["alias_bank"]["additional_query_model_calls"] == 0
    assert data["data"]["forbidden_fresh_issues"] == [270, 287, 326]
    assert data["route_authority"]["gate_can_change_route"] is False
    assert data["route_authority"]["rank2_fallback"] is False
    assert data["route_authority"]["pseudo_route"] is False


def test_reference_registry_has_two_endpoints_per_tool_and_alias_banks() -> None:
    module = _module()
    catalog = module._catalog()
    siblings = module._sibling_map(catalog)

    assert len(catalog) == 16
    assert set(siblings) == {item["route_id"] for item in catalog}
    for item in catalog:
        assert len(item["aliases"]) >= 2
        assert siblings[item["route_id"]] != item["route_id"]
        assert (
            siblings[item["route_id"]].split(".", 1)[0]
            == item["route_id"].split(".", 1)[0]
        )


def test_registry_floor_derivation_is_alias_only() -> None:
    module = _module()
    aliases = {
        "tool.a": ("alpha", "alpha read"),
        "tool.b": ("beta", "beta write"),
    }
    vectors = {
        "tool.a": [[1.0, 0.0], [0.8, 0.6]],
        "tool.b": [[0.0, 1.0], [-0.6, 0.8]],
    }
    siblings = {"tool.a": "tool.b", "tool.b": "tool.a"}

    floors = module._derive_registry_floors(aliases, vectors, siblings)

    assert set(floors) == {"tool.a", "tool.b"}
    assert floors["tool.a"]["route_cohesion_floor"] == 0.8
    assert floors["tool.a"]["route_margin_floor"] >= 0.0
    assert len(floors["tool.a"]["alias_points"]) == 2


def _row(*, own: float, sibling: float, margin_floor: float, cohesion: float):
    return {
        "own_max": own,
        "sibling_max": sibling,
        "query_margin": own - sibling,
        "route_margin_floor": margin_floor,
        "route_cohesion_floor": cohesion,
    }


def test_fixed_rule_families_have_preregistered_semantics() -> None:
    module = _module()

    strong = _row(
        own=0.80,
        sibling=0.20,
        margin_floor=0.30,
        cohesion=0.70,
    )
    contrast_only = _row(
        own=0.60,
        sibling=0.50,
        margin_floor=0.30,
        cohesion=0.70,
    )
    cohesion_only_fail = _row(
        own=0.65,
        sibling=0.20,
        margin_floor=0.30,
        cohesion=0.70,
    )

    assert module._rule_accepts(strong, "A") is True
    assert module._rule_accepts(strong, "B") is True
    assert module._rule_accepts(strong, "C") is True
    assert module._rule_accepts(strong, "D") is True

    assert module._rule_accepts(contrast_only, "A") is True
    assert module._rule_accepts(contrast_only, "B") is False
    assert module._rule_accepts(contrast_only, "C") is False
    assert module._rule_accepts(contrast_only, "D") is False

    assert module._rule_accepts(cohesion_only_fail, "A") is True
    assert module._rule_accepts(cohesion_only_fail, "B") is True
    assert module._rule_accepts(cohesion_only_fail, "C") is False
    assert module._rule_accepts(cohesion_only_fail, "D") is False


def test_negative_registry_margin_is_clamped_to_zero() -> None:
    module = _module()
    aliases = {
        "tool.a": ("a1", "a2"),
        "tool.b": ("b1", "b2"),
    }
    vectors = {
        "tool.a": [[1.0, 0.0], [0.0, 1.0]],
        "tool.b": [[0.8, 0.6], [0.6, 0.8]],
    }
    siblings = {"tool.a": "tool.b", "tool.b": "tool.a"}

    floors = module._derive_registry_floors(aliases, vectors, siblings)

    assert floors["tool.a"]["route_margin_floor_raw"] < 0.0
    assert floors["tool.a"]["route_margin_floor"] == 0.0


def test_candidate_gate_requires_full_quality_parity_and_runtime() -> None:
    module = _module()
    metrics = {
        "supported_exact_route_accuracy": 0.85,
        "near_domain_unsupported_rejection": 0.97,
        "out_of_domain_rejection": 1.0,
        "false_route_rate": 0.01,
    }
    assert module._gate_pass(
        metrics,
        p95_ms=250.0,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )
    assert not module._gate_pass(
        metrics,
        p95_ms=250.01,
        parity_mismatches=0,
        authority_violations=0,
        execution_errors=0,
    )

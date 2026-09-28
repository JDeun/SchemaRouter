from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmarks" / "system-one-candidate-registry.json"


def _load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_system_one_candidate_registry_has_stable_shape() -> None:
    data = _load()

    assert data["schema_version"] == 1
    assert data["updated_at"]
    assert data["purpose"]
    assert data["promotion_gate"] == {
        "supported_exact_route_accuracy_min": 0.85,
        "near_domain_unsupported_rejection_min": 0.97,
        "out_of_domain_rejection": 1.0,
        "false_route_rate_max": 0.01,
        "authority_violations_max": 0,
        "execution_errors_max": 0,
        "target_p95_ms_max": 250,
    }

    allowed_paths = set(data["integration_paths"])
    assert allowed_paths == {
        "system_one_wire",
        "direct_laya",
        "research_callable",
        "reusable_plugin",
    }

    candidates = data["candidates"]
    ids = [item["id"] for item in candidates]
    assert len(ids) == len(set(ids))

    for candidate in candidates:
        assert candidate["id"]
        assert candidate["project"]
        assert candidate["integration_path"] in allowed_paths
        if "fallback_integration_path" in candidate:
            assert candidate["fallback_integration_path"] in allowed_paths
        assert candidate["lifecycle"]
        assert candidate["license_status"]
        assert candidate["schemarouter_status"]


def test_active_research_candidate_is_recorded() -> None:
    data = _load()
    candidates = {item["id"]: item for item in data["candidates"]}

    assert candidates["kev"]["lifecycle"] == "active_research"
    assert "#299" in candidates["kev"]["schemarouter_status"]


def test_discovery_registry_does_not_claim_unmeasured_promotion() -> None:
    data = _load()

    for candidate in data["candidates"]:
        if candidate["lifecycle"] in {"discovery", "archived_discovery"}:
            status = candidate["schemarouter_status"].lower()
            assert (
                "no schemarouter quality evidence" in status
                or "pin one backend/model before benchmark" in status
                or "repository currently archived" in status
            )

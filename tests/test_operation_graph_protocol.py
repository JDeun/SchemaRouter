import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "benchmarks" / "operation-fit-0.10-graph-cycle.json"
BLIND = ROOT / "benchmarks" / "decision-routing-v15-blind-protocol.json"


def test_graph_cycle_is_preregistered_before_implementation() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))

    assert cycle["cycle"] == "0.10-operation-graph-projection-v3"
    assert cycle["status"] == "candidate_frozen_fresh_calibration_allowed"
    assert (
        cycle["development_progress"]["hard_graph_result"]
        == "benchmarks/operation-fit-0.10-graph-hard-dev-result.json"
    )
    assert (
        cycle["development_progress"]["semantic_seed_result"]
        == "benchmarks/operation-fit-0.10-graph-semantic-seed-dev-result.json"
    )
    assert (
        cycle["development_progress"]["semantic_seed_status"]
        == "no_candidate_passed_all_preregistered_gates"
    )
    assert (
        cycle["development_progress"]["propagation_result"]
        == "benchmarks/operation-fit-0.10-graph-propagation-dev-result.json"
    )
    assert (
        cycle["development_progress"]["propagation_status"]
        == "no_candidate_passed_all_preregistered_gates"
    )
    assert (
        cycle["development_progress"]["ranked_bge_result"]
        == "benchmarks/operation-fit-0.10-graph-ranked-bge-dev-result.json"
    )
    assert (
        cycle["development_progress"]["ranked_bge_status"]
        == "no_candidate_passed_all_preregistered_gates"
    )
    assert (
        cycle["development_progress"]["corroboration_result"]
        == "benchmarks/operation-fit-0.10-graph-corroboration-dev-result.json"
    )
    assert (
        cycle["development_progress"]["corroboration_status"]
        == "no_candidate_passed_all_preregistered_gates"
    )
    assert (
        cycle["development_progress"]["static_cache_result"]
        == "benchmarks/operation-fit-0.10-graph-static-cache-dev-result.json"
    )
    assert (
        cycle["development_progress"]["static_cache_status"]
        == "all_preregistered_gates_passed"
    )
    assert (
        cycle["development_progress"]["frozen_candidate"]
        == "benchmarks/operation-fit-0.10-graph-frozen-candidate.json"
    )
    assert (
        cycle["development_progress"]["next_stage"]
        == "fresh frozen-candidate calibration"
    )
    assert (ROOT / "benchmarks" / "operation-fit-0.10-graph-propagation-dev-plan.json").exists()
    assert (ROOT / "benchmarks" / "operation-fit-0.10-graph-ranked-bge-dev-plan.json").exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-corroboration-dev-plan.json"
    ).exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-static-cache-dev-plan.json"
    ).exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-calibration-plan.json"
    ).exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-calibration-attempts.json"
    ).exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-frozen-candidate.json"
    ).exists()
    assert (
        ROOT / "benchmarks" / "operation-fit-0.10-graph-static-cache-dev-result.json"
    ).exists()
    assert (
        ROOT / "scripts" / "generate_decision_routing_graph_calibration_v1.py"
    ).exists()
    assert (ROOT / "scripts" / "compare_graph_calibration.py").exists()
    assert not (
        ROOT / ".github" / "workflows" / "research-operation-graph-semantic-seed.yml"
    ).exists()
    assert not (
        ROOT / ".github" / "workflows" / "research-operation-graph-propagation.yml"
    ).exists()
    assert not (
        ROOT / ".github" / "workflows" / "research-operation-graph-ranked-bge.yml"
    ).exists()
    assert not (
        ROOT / ".github" / "workflows" / "research-operation-graph-corroboration.yml"
    ).exists()
    assert not (
        ROOT / ".github" / "workflows" / "research-operation-graph-static-cache.yml"
    ).exists()
    assert cycle["development_progress"]["candidate_frozen"] is True
    assert cycle["development_progress"]["calibration_allowed"] is True
    assert cycle["development_progress"]["blind_v15_allowed"] is False
    assert cycle["methodology_note"]["hard_graph_latency_promotion_evidence_valid"] is False
    assert cycle["reserved_from_main"] == "526d0c588bbec053fba54c55d982cc67d2a74d56"
    assert cycle["candidate_selection_policy"]["blind_corpus_must_not_exist_before_freeze"] is True
    assert cycle["preregistered_gates"]["promotion_requires_all_gates"] is True
    assert (
        cycle["preregistered_gates"]
        ["false_route_count_must_not_exceed_paired_full_bge_baseline"]
        is True
    )
    assert cycle["preregistered_gates"]["paired_p95_latency_must_not_exceed_full_bge"] is True
    attempts = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-fit-0.10-graph-calibration-attempts.json"
        ).read_text(encoding="utf-8")
    )
    invalidated = attempts["invalidated_attempts"][0]
    assert invalidated["workflow_run_id"] == 36285424108
    assert invalidated["metrics_inspected"] is False
    assert invalidated["artifact_contents_inspected"] is False
    assert invalidated["tuning_use"] is False


def test_graph_authority_is_stricter_than_semantic_evidence() -> None:
    cycle = json.loads(CYCLE.read_text(encoding="utf-8"))
    principles = " ".join(cycle["architectural_principles"]).lower()

    assert "graph topology is the routing authority" in principles
    assert "soft evidence" in principles
    assert "cannot create tools" in principles
    assert "uncertainty band" in principles


def test_v15_is_reserved_but_not_generated() -> None:
    blind = json.loads(BLIND.read_text(encoding="utf-8"))

    assert blind["version"] == "v15"
    assert blind["status"] == "reserved_not_generated"
    assert blind["corpus_exists"] is False
    assert blind["tuning_eligible"] is False
    assert "v13 consumed blind-final corpus" in blind["selection_policy"]["forbidden_for_selection"]
    assert "retired v14 reservation" in blind["selection_policy"]["forbidden_for_selection"]

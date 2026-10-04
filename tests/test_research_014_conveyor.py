from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_utility_prior_query_guard import queries_from_corpus
from scripts.generate_agent_utility_v3_heldout_corpus import (
    build_corpus as build_heldout,
)
from scripts.generate_agent_utility_v4_final_answer_corpus import (
    build_corpus as build_final,
)
from scripts.generate_agent_utility_v6_corrective_corpus import (
    build_corpus as build_corrective,
)
from scripts.research_014_conveyor import (
    DOWNSTREAM_IMPLEMENTATION_SHA,
    StageRun,
    combine_digests,
    retry_infrastructure_failure,
    source_sha_from_run,
    stale_pending_wrapper,
)
from scripts.validate_agent_utility_v3_heldout_corpus import (
    validate_corpus as validate_heldout,
)
from scripts.validate_agent_utility_v4_final_answer_corpus import (
    validate_corpus as validate_final,
)
from scripts.validate_agent_utility_v6_corrective_corpus import (
    validate_corpus as validate_corrective,
)


def test_downstream_corpora_build_and_validate(tmp_path: Path) -> None:
    corrective = build_corrective("a" * 40)
    corrective_summary = validate_corrective(corrective)
    assert corrective_summary["task_count"] == 180

    heldout = build_heldout(
        "b" * 40,
        include_struct_fixed3=True,
        include_state_aware=True,
    )
    heldout_summary = validate_heldout(heldout)
    assert heldout_summary["task_count"] == 780
    assert heldout["condition_manifest"]["optional_promoted_conditions"] == [
        "STRUCT-FIXED-3",
        "SR-5-STATE-AWARE",
    ]

    heldout_path = tmp_path / "heldout.json"
    heldout_path.write_text(
        json.dumps(heldout, ensure_ascii=False),
        encoding="utf-8",
    )
    forbidden = queries_from_corpus(heldout_path)

    final = build_final(
        "c" * 40,
        forbidden_corpus=heldout_path,
    )
    final_summary = validate_final(
        final,
        extra_forbidden_queries=forbidden,
    )
    assert final_summary["task_count"] == 144
    assert all(
        task["corrective_contract"]["initial_candidate_miss"] is True
        for task in final["tasks"]
        if task["answer_task_stratum"] == "corrective_expansion_required"
    )


def test_conveyor_digest_is_ordered_and_stable() -> None:
    left = combine_digests("sha256:a", "sha256:b")
    assert left == combine_digests("sha256:a", "sha256:b")
    assert left != combine_digests("sha256:b", "sha256:a")
    assert left.startswith("sha256:")
    assert len(left) == 71


def test_conveyor_workflows_encode_expected_stage_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    conveyor = (
        root / ".github" / "workflows" / "research-0.14-conveyor.yml"
    ).read_text(encoding="utf-8")
    corrective = (
        root
        / ".github"
        / "workflows"
        / "research-0.14-corrective-reretrieval.yml"
    ).read_text(encoding="utf-8")
    heldout = (
        root
        / ".github"
        / "workflows"
        / "research-0.14-heldout-generalization.yml"
    ).read_text(encoding="utf-8")
    final = (
        root / ".github" / "workflows" / "research-0.14-final-answer.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "17 * * * *"' in conveyor
    assert "Research 0.14 B2 SmolLM3 Full" in conveyor
    assert "Research 0.14 Structural K3 Agent Utility" in conveyor
    assert "Research 0.14 Corrective Re-retrieval" in conveyor
    assert "Research 0.14 Held-out Generalization" in conveyor
    assert "Research 0.14 Final Answer" in conveyor

    assert "CANONICAL_B2_RUN" in corrective
    assert "evidence_digest" in corrective
    assert "include_struct_fixed3" in heldout
    assert "include_state_aware" in heldout
    assert "heldout_run_id" in final
    assert "--forbidden-corpus" in final


class _RetryAPI:
    def __init__(self) -> None:
        self.rerun_ids: list[int] = []

    def rerun_failed_jobs(self, run_id: int) -> None:
        self.rerun_ids.append(run_id)


def test_infrastructure_retry_preserves_run_and_is_bounded() -> None:
    api = _RetryAPI()
    actions: list[str] = []
    failed = StageRun(
        id=77,
        status="completed",
        conclusion="failure",
        display_title="fixture",
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=1,
        head_sha="a" * 40,
    )
    assert retry_infrastructure_failure(
        api, failed, execute=True, actions=actions, label="fixture"
    )
    assert api.rerun_ids == [77]
    assert actions == ["rerun_failed_fixture:run=77:attempt=2"]

    exhausted = StageRun(
        id=78,
        status="completed",
        conclusion="failure",
        display_title="fixture",
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=3,
        head_sha="b" * 40,
    )
    assert not retry_infrastructure_failure(
        api, exhausted, execute=True, actions=actions, label="fixture"
    )
    assert api.rerun_ids == [77]


def test_conveyor_contract_avoids_k3_trigger_race_and_has_recovery() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "scripts" / "research_014_conveyor.py").read_text(
        encoding="utf-8"
    )
    workflow = (
        root / ".github" / "workflows" / "research-0.14-conveyor.yml"
    ).read_text(encoding="utf-8")

    assert "wait_for_k3_native_trigger" in controller
    assert "recover_missing_k3" in controller
    assert "rerun_failed_jobs" in controller
    assert "--recover-missing-k3" in workflow
    assert 'EVENT_NAME: "${{ github.event_name }}"' in workflow
    assert "research-0.14-conveyor-state-" in workflow


def test_only_one_downstream_workflow_set_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    workflows = root / ".github" / "workflows"
    assert not (workflows / "research-0.14-corrective.yml").exists()
    assert not (workflows / "research-0.14-heldout.yml").exists()
    assert not (root / "scripts" / "research_0_14_conveyor.py").exists()


def test_source_sha_from_run_prefers_explicit_run_marker() -> None:
    run = StageRun(
        id=90,
        status="completed",
        conclusion="failure",
        display_title=(
            "Research 0.14 Corrective sha256:fixture "
            "source=" + "c" * 40
        ),
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=1,
        head_sha="d" * 40,
    )
    assert source_sha_from_run(run) == "c" * 40


def test_source_sha_from_run_falls_back_to_first_attempt_head() -> None:
    run = StageRun(
        id=91,
        status="completed",
        conclusion="failure",
        display_title="Research 0.14 Corrective sha256:fixture",
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=1,
        head_sha="e" * 40,
    )
    assert source_sha_from_run(run) == "e" * 40


def test_downstream_scientific_source_is_frozen_to_conveyor_merge() -> None:
    assert DOWNSTREAM_IMPLEMENTATION_SHA == (
        "30663de8f618bc88a893d9bf6214035a70e8e894"
    )


def test_downstream_failures_use_fresh_wrapper_dispatch_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "scripts" / "research_014_conveyor.py").read_text(
        encoding="utf-8"
    )
    assert "recover_dispatch_corrective_after_failure" in controller
    assert "recover_dispatch_heldout_after_failure" in controller
    assert "recover_dispatch_final_after_failure" in controller


def test_stale_pending_wrapper_recovery_preserves_scientific_source_contract() -> None:
    queued = StageRun(
        id=92,
        status="queued",
        conclusion=None,
        display_title=(
            "Research 0.14 Corrective sha256:fixture "
            "source=" + "c" * 40
        ),
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=1,
        head_sha="d" * 40,
    )
    assert stale_pending_wrapper(
        queued,
        wrapper_sha="e" * 40,
        min_age_seconds=0.0,
    )
    assert not stale_pending_wrapper(
        queued,
        wrapper_sha="d" * 40,
        min_age_seconds=0.0,
    )
    assert source_sha_from_run(queued) == "c" * 40

    pending = StageRun(
        id=93,
        status="pending",
        conclusion=None,
        display_title=(
            "Research 0.14 Corrective sha256:fixture "
            "source=" + "c" * 40
        ),
        created_at="2026-09-30T00:00:00Z",
        html_url="",
        run_attempt=1,
        head_sha="d" * 40,
    )
    assert stale_pending_wrapper(
        pending,
        wrapper_sha="e" * 40,
        min_age_seconds=0.0,
    )


def test_downstream_workflows_recover_model_cache_eviction() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow_names = (
        "research-0.14-corrective-reretrieval.yml",
        "research-0.14-heldout-generalization.yml",
        "research-0.14-final-answer.yml",
        "research-0.14-field-projection.yml",
    )
    cache_sha = "0057852bfaa89a56745cba8c7296529d2fc39830"

    for name in workflow_names:
        workflow = (root / ".github" / "workflows" / name).read_text(
            encoding="utf-8"
        )
        assert f"uses: actions/cache/save@{cache_sha}" in workflow
        assert workflow.count(f"uses: actions/cache/restore@{cache_sha}") == 2
        assert "fail-on-cache-miss: true" not in workflow
        assert "Recover exact model revision after cache eviction" in workflow
        assert 'revision=os.environ["B2_REVISION"]' in workflow


def test_conveyor_can_supersede_stale_pending_corrective_wrapper() -> None:
    root = Path(__file__).resolve().parents[1]
    controller = (root / "scripts" / "research_014_conveyor.py").read_text(
        encoding="utf-8"
    )
    assert "recover_dispatch_stale_pending_corrective_wrapper" in controller
    assert "stale_pending_wrapper(corrective, wrapper_sha=_wrapper_sha)" in controller


def test_issue_15_is_registered_as_nonblocking_external_dag_node() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (
            root
            / "benchmarks"
            / "agent-utility-0.14-conveyor-preregistration.json"
        ).read_text(encoding="utf-8")
    )

    assert "#15_LIVE_DECISION_EVIDENCE" in manifest["independent_stages"]
    node = manifest["external_evidence_nodes"]["15"]
    assert node["tracking_issue"] == 15
    assert node["blocking"] is False
    assert node["automatic_dispatch"] is False
    assert node["harness"] == "scripts/benchmark_decision_routing.py"

    policy = manifest["launch_policy"]
    assert policy["issue_15_live_decision_evidence_is_independent"] is True
    assert policy["issue_15_must_not_block_frozen_agent_utility_chain"] is True
    assert policy["issue_15_automatic_dispatch"] is False

    amendment = next(
        row for row in manifest["amendments"] if row.get("issue") == 15
    )
    assert "terminal evidence digest definition" in amendment["explicitly_unchanged"]
    assert amendment["automatic_dispatch"] is False

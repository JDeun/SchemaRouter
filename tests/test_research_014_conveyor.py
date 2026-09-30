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
    StageRun,
    combine_digests,
    retry_infrastructure_failure,
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

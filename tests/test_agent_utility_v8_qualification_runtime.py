"""Workflow-independent tests for the #510 qualification runtime."""
from __future__ import annotations

import json

import pytest

from scripts.aggregate_agent_utility_v8_qualification import aggregate
from scripts.generate_agent_utility_v8_qualification_corpus import (
    build_qualification_corpus,
)
from scripts.qualify_agent_utility_runtime import ROSTER, ROSTER_REVISIONS
from scripts.select_agent_utility_v8_runtime import select


def _row(task_id: str, *, passing: bool) -> dict:
    return {
        "semantic_task_id": task_id,
        "final_envelope_valid": passing,
        "tool_call_count": 1 if passing else 0,
        "required_fact_recall": 1.0 if passing else 0.0,
    }


def _write_shards(tmp_path, corpus, candidate: str, *, passing: bool) -> None:
    revision = ROSTER_REVISIONS[candidate]
    tasks = corpus["tasks"]
    for shard_index in range(0, len(tasks), 6):
        subset = tasks[shard_index : shard_index + 6]
        payload = {
            "schema_version": 1,
            "evidence_class": corpus["evidence_class"],
            "surface": corpus["surface"],
            "source_revision": corpus["source_revision"],
            "harness_revision": corpus["source_revision"],
            "corpus_tasks_sha256": corpus["tasks_sha256"],
            "candidate_model": candidate,
            "model_revision": revision,
            "runtime": {
                "candidate_model": candidate,
                "model_revision": revision,
                "platform": {
                    "python": "3.12.14",
                    "machine": "aarch64",
                    "torch": "2.14.0+cpu",
                    "transformers": "4.57.6",
                },
            },
            "rows": [
                _row(str(task["semantic_task_id"]), passing=passing)
                for task in subset
            ],
        }
        path = tmp_path / f"shard-{shard_index // 6:02d}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")


def _write_evidence(tmp_path, evidence: dict, index: int) -> None:
    path = tmp_path / f"evidence-{index}.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")


def test_aggregate_builds_a_provenance_valid_qualified_evidence(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    candidate = ROSTER[0]
    _write_shards(tmp_path, corpus, candidate, passing=True)

    result = aggregate(corpus, candidate=candidate, shard_dir=tmp_path)

    assert result["qualified"] is True
    assert result["episode_count"] == 36
    assert result["rates"] == {
        "envelope_valid_rate": 1.0,
        "tool_call_rate": 1.0,
        "grounded_fact_rate": 1.0,
    }


def test_aggregate_refuses_missing_frozen_rows(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    candidate = ROSTER[0]
    _write_shards(tmp_path, corpus, candidate, passing=True)
    (tmp_path / "shard-05.json").unlink()

    with pytest.raises(ValueError, match="do not cover frozen surface"):
        aggregate(corpus, candidate=candidate, shard_dir=tmp_path)


def test_selector_returns_the_first_qualifier(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    shard_dir = tmp_path / "first"
    shard_dir.mkdir()
    _write_shards(shard_dir, corpus, ROSTER[0], passing=True)
    evidence = aggregate(corpus, candidate=ROSTER[0], shard_dir=shard_dir)

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_evidence(evidence_dir, evidence, 0)
    result = select(corpus, evidence_dir=evidence_dir)

    assert result["selected_runtime"] == ROSTER[0]
    assert result["evaluated_candidates"] == [ROSTER[0]]
    assert result["roster_exhausted"] is False


def test_selector_allows_next_candidate_only_after_measured_failure(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    for index, (candidate, passing) in enumerate(
        ((ROSTER[0], False), (ROSTER[1], True))
    ):
        shard_dir = tmp_path / f"candidate-{index}"
        shard_dir.mkdir()
        _write_shards(shard_dir, corpus, candidate, passing=passing)
        evidence = aggregate(corpus, candidate=candidate, shard_dir=shard_dir)
        _write_evidence(evidence_dir, evidence, index)

    result = select(corpus, evidence_dir=evidence_dir)
    assert result["selected_runtime"] == ROSTER[1]
    assert result["evaluated_candidates"] == [ROSTER[0], ROSTER[1]]


def test_selector_refuses_an_incomplete_failed_prefix(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    shard_dir = tmp_path / "first"
    shard_dir.mkdir()
    _write_shards(shard_dir, corpus, ROSTER[0], passing=False)
    evidence = aggregate(corpus, candidate=ROSTER[0], shard_dir=shard_dir)

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_evidence(evidence_dir, evidence, 0)

    with pytest.raises(ValueError, match="incomplete roster prefix"):
        select(corpus, evidence_dir=evidence_dir)


def test_workflow_keeps_candidates_strictly_sequential_and_revision_pinned():
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-0.14-runtime-qualification.yml"
    ).read_text(encoding="utf-8")

    assert 'QUAL_REV: "a07cc9a04f16550a088caea529712d1d335b0ac1"' in workflow
    assert 'QUAL_REV: "1cfa9a7208912126459214e8b04321603b3df60c"' in workflow
    assert 'QUAL_REV: "b968826d9c46dd6066d109eabc6255188de91218"' in workflow

    assert "needs.aggregate-smollm3.outputs.qualified != 'true'" in workflow
    assert "needs.aggregate-qwen4.outputs.qualified != 'true'" in workflow
    assert 'B2_ATTN_IMPLEMENTATION: "sdpa"' in workflow
    assert 'ref: "${{ env.SOURCE_SHA }}"' in workflow



def test_workflow_publishes_model_cache_before_evaluator_fanout():
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-0.14-runtime-qualification.yml"
    ).read_text(encoding="utf-8")

    # Cache warm-up jobs must commit the exact-revision cache as a normal step,
    # not rely on the generic cache action's post-job save. Downstream matrix
    # jobs otherwise can race cache visibility and fail before inference.
    assert workflow.count(
        "uses: actions/cache/save@0057852bfaa89a56745cba8c7296529d2fc39830"
    ) == 3
    assert workflow.count(
        "uses: actions/cache/restore@0057852bfaa89a56745cba8c7296529d2fc39830"
    ) == 6
    assert "Publish exact candidate cache before fan-out" in workflow
    assert "uses: actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830" not in workflow

def test_workflow_downloads_qualification_corpus_at_repo_root():
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-0.14-runtime-qualification.yml"
    ).read_text(encoding="utf-8")

    # The qualification artifact contains repo-root-relative paths for both
    # artifacts/qualification/... and benchmarks/.... Downloading it under
    # artifacts/qualification would double-nest the corpus path and fail before inference.
    download_blocks = workflow.split("uses: actions/download-artifact@")[1:]
    qualification_blocks = [
        block
        for block in download_blocks
        if 'name: "qualification-corpus-${{ github.run_id }}"' in block
    ]
    assert qualification_blocks
    assert all("\n          path: .\n" in block for block in qualification_blocks)
    assert all(
        "\n          path: artifacts/qualification\n" not in block
        for block in qualification_blocks
    )

def test_workflow_launch_is_armed_only_by_the_explicit_trigger_file():
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-0.14-runtime-qualification.yml"
    ).read_text(encoding="utf-8")

    assert ".github/research-510-runtime-qualification-trigger.json" in workflow
    assert "paths:" in workflow


def test_smollm3_qualification_reuses_the_exact_canonical_b2_runtime_revision():
    from scripts.evaluate_agent_utility_phase_b_smollm3 import (
        MODEL_NAME,
        MODEL_REVISION,
    )

    assert MODEL_NAME == ROSTER[0]
    assert MODEL_REVISION == ROSTER_REVISIONS[ROSTER[0]]


def test_selector_reports_recomputed_rates_not_untrusted_evidence_summary(tmp_path) -> None:
    corpus = build_qualification_corpus("a" * 40)
    shard_dir = tmp_path / "first"
    shard_dir.mkdir()
    _write_shards(shard_dir, corpus, ROSTER[0], passing=True)
    evidence = aggregate(corpus, candidate=ROSTER[0], shard_dir=shard_dir)
    evidence["rates"] = {
        "envelope_valid_rate": 0.0,
        "tool_call_rate": 0.0,
        "grounded_fact_rate": 0.0,
    }

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_evidence(evidence_dir, evidence, 0)

    result = select(corpus, evidence_dir=evidence_dir)
    assert result["selected_runtime"] == ROSTER[0]
    assert result["rates_by_candidate"][ROSTER[0]] == {
        "envelope_valid_rate": 1.0,
        "tool_call_rate": 1.0,
        "grounded_fact_rate": 1.0,
    }

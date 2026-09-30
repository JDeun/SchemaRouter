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

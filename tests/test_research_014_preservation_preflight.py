"""Read-only live 0.14 original-workflow artifact preservation tests."""

from __future__ import annotations

import pytest

from scripts.research_014_heldout_recovery import FROZEN_SOURCE, frozen_shards
from scripts.research_014_preservation_preflight import inspect_parent


def frozen_corpus():
    return {
        "benchmark": "heldout",
        "generator_source_revision": FROZEN_SOURCE,
        "tasks_sha256": "a" * 64,
        "tasks": [{"semantic_task_id": f"t{i:04d}"} for i in range(780)],
        "condition_manifest": {"conditions": ["FULL", "SR-5", "ORACLE"]},
    }


def complete_payload(corpus, catalog, ids):
    return {
        "issue": 432,
        "benchmark": corpus["benchmark"],
        "generator_source_revision": FROZEN_SOURCE,
        "tasks_sha256": corpus["tasks_sha256"],
        "catalog_size": catalog,
        "task_ids": sorted(ids),
        "conditions": corpus["condition_manifest"]["conditions"],
        "model": {
            "name": "HuggingFaceTB/SmolLM3-3B",
            "revision": "a07cc9a04f16550a088caea529712d1d335b0ac1",
            "attention_implementation": "sdpa",
            "max_new_tokens": 256,
            "max_turns": 6,
            "seed": 20260929,
            "threads": 4,
        },
        "runtime": {
            "machine": "aarch64",
            "python": "3.12.14",
            "jinja2": "3.1.6",
            "tokenizers": "0.22.2",
            "safetensors": "0.8.0",
            "torch": "2.14.0+cpu",
            "transformers": "4.57.6",
        },
        "rows": [
            {"task_id": task, "catalog_size": catalog, "condition": condition}
            for task in ids
            for condition in corpus["condition_manifest"]["conditions"]
        ],
    }


class SnapshotAPI:
    def __init__(self):
        ids = sorted(frozen_shards(frozen_corpus()))
        self.jobs = [
            {"name": "prepare", "status": "completed", "conclusion": "success"},
            {"name": "model-cache", "status": "completed", "conclusion": "success"},
        ]
        for shard in ids:
            conclusion = (
                "success"
                if shard in {"c100-g00", "c100-g01"}
                else "cancelled"
                if shard == "c250-g00"
                else None
            )
            self.jobs.append({
                "name": f"evaluate ({shard}, tasks...)",
                "status": "completed" if conclusion else "queued",
                "conclusion": conclusion,
            })
        self.artifact_rows = [
            {
                "name": f"heldout-shard-{shard}-123",
                "id": i + 1,
                "digest": "sha256:" + "b" * 64,
                "expired": False,
            }
            for i, shard in enumerate(["c100-g00", "c100-g01", "c250-g00"])
        ]

    def run(self, _):
        return {
            "status": "queued",
            "path": ".github/workflows/research-0.14-heldout-generalization.yml",
            "display_title": f"Frozen held-out source={FROZEN_SOURCE}",
        }

    def get(self, path):
        page = int(path.rsplit("page=", 1)[-1])
        return {"jobs": self.jobs[(page - 1) * 100:page * 100]}

    def artifacts(self, _):
        return self.artifact_rows


def test_read_only_preflight_retains_only_successful_complete_artifacts(monkeypatch):
    from scripts import research_014_preservation_preflight as module

    corpus = frozen_corpus()
    frozen = frozen_shards(corpus)
    monkeypatch.setattr(
        module,
        "_artifact_payload",
        lambda _api, _artifact, filename: complete_payload(
            corpus, *frozen[filename.removesuffix(".json")]
        ),
    )
    api = SnapshotAPI()
    report = inspect_parent(api, corpus, parent=123)
    assert report["safe_to_cancel"] is False
    assert report["scientific_aggregate"] is False
    assert report["run_is_still_mutating"] is True
    assert report["verified_reusable_parent_shards"] == 2
    assert report["verified_reusable_episodes"] == 60
    assert report["missing_or_incomplete_parent_shards_at_snapshot"] == 232
    assert report["latest_evaluator_status_counts"]["cancelled"] == 1
    assert len(report["prospective_recovery_waves"]) == 5
    assert sum(w["microshards"] for w in report["prospective_recovery_waves"]) == 1160
    assert set(report["verified_artifact_provenance"]) == {"c100-g00", "c100-g01"}


def test_corrupt_success_artifact_fails_reuse_not_entire_preflight(monkeypatch):
    from scripts import research_014_preservation_preflight as module

    corpus = frozen_corpus()
    frozen = frozen_shards(corpus)

    def corrupted(_api, _artifact, filename):
        if filename == "c100-g00.json":
            raise ValueError("ZIP digest mismatch")
        return complete_payload(corpus, *frozen[filename.removesuffix(".json")])

    monkeypatch.setattr(module, "_artifact_payload", corrupted)
    report = inspect_parent(SnapshotAPI(), corpus, parent=123)
    assert report["verified_reusable_parent_shards"] == 1
    assert report["invalid_successful_shard_artifacts"] == {"c100-g00": "ValueError"}


def test_duplicate_evaluator_identity_is_never_accepted():
    api = SnapshotAPI()
    api.jobs.append(dict(api.jobs[2]))
    with pytest.raises(ValueError, match="duplicate"):
        inspect_parent(api, frozen_corpus(), parent=123)

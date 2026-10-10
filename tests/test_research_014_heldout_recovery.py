"""Frozen 0.14 held-out recovery contract tests."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.research_014_heldout_recovery import (
    FROZEN_SOURCE,
    collect,
    frozen_shards,
    plan,
    successful_parent_shards,
    validate_shard,
    wave_parts,
)


def corpus():
    return {
        "benchmark": "heldout",
        "generator_source_revision": FROZEN_SOURCE,
        "tasks_sha256": "a" * 64,
        "tasks": [{"semantic_task_id": f"t{i:04d}"} for i in range(780)],
        "condition_manifest": {"conditions": ["FULL", "SR-5", "ORACLE"]},
    }


def artifact(shard, run=123, *, expired=False):
    return {"name": f"heldout-shard-{shard}-{run}", "id": 1,
            "digest": "sha256:" + "a" * 64, "expired": expired}


def job(shard, conclusion):
    return {"name": f"evaluate ({shard}, 100, tasks...", "status": "completed",
            "conclusion": conclusion}


def payload(data, catalog, task_ids):
    return {
        "issue": 432, "benchmark": data["benchmark"],
        "generator_source_revision": FROZEN_SOURCE,
        "tasks_sha256": data["tasks_sha256"],
        "catalog_size": catalog, "task_ids": list(task_ids),
        "conditions": data["condition_manifest"]["conditions"],
        "model": {"name": "HuggingFaceTB/SmolLM3-3B",
                  "revision": "a07cc9a04f16550a088caea529712d1d335b0ac1",
                  "attention_implementation": "sdpa",
                  "max_new_tokens": 256, "max_turns": 6,
                  "seed": 20260929, "threads": 4},
        "runtime": {"machine": "aarch64", "python": "3.12.14",
                    "jinja2": "3.1.6", "tokenizers": "0.22.2",
                    "safetensors": "0.8.0",
                    "torch": "2.14.0+cpu", "transformers": "4.57.6"},
        "rows": [
            {"task_id": task, "catalog_size": catalog, "condition": cond,
             "passed": False}
            for task in task_ids for cond in data["condition_manifest"]["conditions"]
        ],
    }


def test_partition_preserves_all_780_tasks_and_234_scientific_shards():
    shards = frozen_shards(corpus())
    assert len(shards) == 234
    assert len(set(task for _, tasks in shards.values() for task in tasks)) == 780
    missing = sorted(shards)[:81]
    wave0, n = wave_parts(shards, missing, 0)
    wave1, _ = wave_parts(shards, missing, 1)
    wave2, _ = wave_parts(shards, missing, 2)
    assert n == 3
    assert tuple(map(len, (wave0, wave1, wave2))) == (200, 200, 5)
    assert all(len(m["task_ids"].split(",")) == 2 for m in wave0 + wave1 + wave2)
    assert len({m["job_id"] for m in wave0 + wave1 + wave2}) == 405
    for invalid in (3, -1):
        with pytest.raises(ValueError):
            wave_parts(shards, missing, invalid)
    with pytest.raises(ValueError):
        wave_parts(shards, [missing[0], missing[0]], 0)


def test_timed_out_job_artifact_is_not_a_success():
    shards = successful_parent_shards(
        [job("c250-g01", "cancelled"), job("c250-g08", "success")],
        [artifact("c250-g01"), artifact("c250-g08")], 123,
    )
    assert shards == {"c250-g08"}
    assert successful_parent_shards([job("c250-g08", "success")],
                                    [artifact("c250-g08", expired=True)], 123) == set()


def test_partial_duplicate_and_model_drift_are_rejected():
    data = corpus()
    tasks = ("t0000", "t0001")
    full = payload(data, 250, tasks)
    validate_shard(full, corpus=data, catalog=250, task_ids=tasks)
    partial = copy.deepcopy(full)
    partial["rows"].pop()
    with pytest.raises(ValueError):
        validate_shard(partial, corpus=data, catalog=250, task_ids=tasks)
    duplicate = copy.deepcopy(full)
    duplicate["rows"][-1] = duplicate["rows"][0]
    with pytest.raises(ValueError):
        validate_shard(duplicate, corpus=data, catalog=250, task_ids=tasks)
    drift = copy.deepcopy(full)
    drift["model"]["revision"] = "changed"
    with pytest.raises(ValueError):
        validate_shard(drift, corpus=data, catalog=250, task_ids=tasks)


class StubAPI:
    def __init__(self, terminal):
        self.terminal = terminal
        self.jobs = ([{"name": "prepare", "conclusion": "success"},
                      {"name": "model-cache", "conclusion": "success"}] +
                     [job(shard, "success") for shard in frozen_shards(corpus())])
        self.jobs[2]["conclusion"] = "cancelled"
    def run(self, run_id):
        return {
            "path": ".github/workflows/research-0.14-heldout-generalization.yml",
            "status": "completed" if self.terminal else "queued",
            "display_title": f"Research 0.14 Held-out sha256:test source={FROZEN_SOURCE}",
        }
    def get(self, path):
        page = int(path.rsplit("page=", 1)[-1])
        return {"jobs": self.jobs[(page-1)*100:page*100]}
    def artifacts(self, run_id):
        return [artifact(shard) for shard in frozen_shards(corpus())]


def test_plan_refuses_active_parent_and_recovers_only_cancelled_shard(monkeypatch):
    import scripts.research_014_heldout_recovery as module

    data = corpus()
    shards = frozen_shards(data)

    def read_valid_parent(_api, _artifact, filename):
        catalog, task_ids = shards[filename[:-5]]
        return payload(data, catalog, task_ids)

    monkeypatch.setattr(module, "_artifact_payload", read_valid_parent)
    args = dict(parent=123, wave=0, source=FROZEN_SOURCE, digest="sha256:test")
    with pytest.raises(ValueError, match="preserve"):
        plan(StubAPI(False), data, **args)
    p = plan(StubAPI(True), data, **args)
    assert len(p["successful_parent_shards"]) == 233
    assert p["missing_parent_shards"] == ["c100-g00"]
    assert len(p["matrix"]) == 5


def test_workflow_keeps_exact_frozen_scientific_source():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/research-0.14-heldout-recovery.yml").read_text()
    assert 'ref: "${{ inputs.source_sha }}"' in workflow
    assert "scripts/evaluate_agent_utility_v3_heldout.py" in workflow
    assert "scientific/scripts/aggregate_agent_utility_v3_heldout.py" in workflow
    assert "max-parallel: 32" in workflow
    final = (root / ".github/workflows/research-0.14-final-answer.yml").read_text()
    assert "Export all 144 frozen final-answer microshards" in final
    assert "ids[index:index + 2] for index in range(0, len(ids), 2)" in final
    assert "assert len(include) == 144" in final
    assert "max-parallel: 32" in final
    assert 'ref: "${{ inputs.source_sha }}"' in final

    assert "heldout-generalization-canonical-${{ github.run_id }}" in workflow


def test_complete_heldout_salvage_reuses_successes_and_rejects_missing_part(
    tmp_path, monkeypatch,
):
    import scripts.research_014_heldout_recovery as module

    data = corpus()
    shards = frozen_shards(data)

    def read_valid_parent(_api, _artifact, filename):
        catalog, task_ids = shards[filename[:-5]]
        return payload(data, catalog, task_ids)

    monkeypatch.setattr(module, "_artifact_payload", read_valid_parent)
    parent_plan = plan(
        StubAPI(True), data, parent=123, wave=0,
        source=FROZEN_SOURCE, digest="sha256:test",
    )
    selected = parent_plan["matrix"]

    class CollectAPI(StubAPI):
        def __init__(self):
            super().__init__(True)
            self.recovered = [
                {"name": f"heldout-recovery-part-{part['job_id']}-456",
                 "id": 1000 + i, "digest": "sha256:" + "b" * 64,
                 "expired": False}
                for i, part in enumerate(selected)
            ]
        def artifacts(self, run_id):
            if run_id == 456:
                return self.recovered
            return super().artifacts(run_id)
        def workflow_runs(self, filename):
            assert filename == module.RECOVERY_WORKFLOW
            return [{
                "id": 456, "status": "in_progress",
                "display_title": (
                    f"Held-out recovery parent=123 wave=0 source={FROZEN_SOURCE}"
                ),
            }]

    def load_artifact(_api, _artifact, filename):
        ident = filename[:-5]
        if "-p" in ident:
            shard, part = ident.rsplit("-p", 1)
            catalog, tasks = shards[shard]
            tasks = tasks[int(part) * 2:int(part) * 2 + 2]
        else:
            catalog, tasks = shards[ident]
        return payload(data, catalog, tasks)

    monkeypatch.setattr(module, "_artifact_payload", load_artifact)
    api = CollectAPI()
    result = collect(api, data, parent_plan, current_recovery_run=456,
                     out=tmp_path / "full")
    assert result["episode_count"] == 780 * 3 * 3
    assert result["parent_success_count"] == 233
    assert result["recovered_parent_count"] == 1
    assert len(result["artifacts"]) == 233 + 5
    assert "c100-g00" not in result["artifacts"]
    api.recovered.pop()
    with pytest.raises(ValueError, match="incomplete recovery wave"):
        collect(api, data, parent_plan, current_recovery_run=456,
                out=tmp_path / "missing")

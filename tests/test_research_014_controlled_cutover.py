"""Cutover must fail closed, preserve completed ZIPs, and never score rows."""
from __future__ import annotations

import copy

import pytest

from scripts import research_014_controlled_cutover as cut


def sample_corpus() -> dict:
    return {"tasks_sha256": "a" * 64}


class FakeAPI:
    def __init__(self):
        self.status = "queued"
        self.pilot_status = "completed"
        self.pilot_conclusion = "success"
        self.pilot_head = cut.PILOT_SHA
        self.job_conclusions = {name: "success" for name in cut.PILOT_PARTS}
        self.cancel_requests = 0
        self.available_paths = True
        self.reads = 0

    def run(self, run_id):
        self.reads += 1
        if run_id == cut.PILOT_RUN:
            return {
                "status": self.pilot_status,
                "conclusion": self.pilot_conclusion,
                "head_sha": self.pilot_head,
            }
        assert run_id == cut.ORIGINAL_RUN
        return {
            "status": self.status,
            "path": ".github/workflows/research-0.14-heldout-generalization.yml",
            "display_title": (
                "Research 0.14 Held-out " + cut.EVIDENCE_DIGEST
                + " source=" + cut.FROZEN_SOURCE
            ),
        }

    def path_exists(self, path, *, ref):
        assert ref == "main"
        return self.available_paths

    def artifacts(self, run_id):
        assert run_id == cut.PILOT_RUN
        return [
            {
                "name": (
                    f"frozen-two-task-speed-pilot-{name}-{cut.PILOT_RUN}"
                ),
                "id": idx + 1,
                "digest": "sha256:" + "f" * 64,
                "expired": False,
            }
            for idx, name in enumerate(cut.PILOT_PARTS)
        ]

    def _request(self, method, path):
        assert (method, path) == (
            "POST", f"/actions/runs/{cut.ORIGINAL_RUN}/cancel"
        )
        self.cancel_requests += 1
        return 202, b""


def fake_jobs(_api, run):
    assert run == cut.PILOT_RUN
    return [
        {"name": f"measure ({name}, 500, example)",
         "status": "completed", "conclusion": status}
        for name, status in _api.job_conclusions.items()
    ]


def fake_pilot_payload(api, artifact, filename):
    assert filename == "pilot-report.json"
    name = artifact["name"]
    prefix = "frozen-two-task-speed-pilot-"
    label = name[len(prefix):].removesuffix(f"-{cut.PILOT_RUN}")
    return {
        "job_id": label,
        "catalog_size": cut.PILOT_PARTS[label],
        "source_revision": cut.FROZEN_SOURCE,
        "parent_run_id": cut.ORIGINAL_RUN,
        "tasks_sha256": "a" * 64,
        "identity_only_pilot": True,
        "eligible_for_scientific_aggregation": False,
        "verified_episode_count": 10,
        "tasks": ["t0", "t1"],
        "conditions": sorted(cut.REQUIRED_CONDITIONS),
        "evaluation_wall_seconds": 6000,
        "runtime": {
            "python": "3.12.14",
            "machine": "aarch64",
            "torch": "2.14.0+cpu",
            "transformers": "4.57.6",
        },
    }


def fake_inspect(api, corpus, *, parent):
    assert parent == cut.ORIGINAL_RUN
    return {
        "kind": "read_only_preservation_preflight",
        "source_sha": cut.FROZEN_SOURCE,
        "tasks_sha256": corpus["tasks_sha256"],
        "expected_parent_shards": 234,
        "latest_evaluator_status_counts": {
            "success": 97,
            "in_progress": 16,
            "queued": 111,
            "failure": 1,
            "cancelled": 9,
            "timed_out": 0,
        },
        "verified_reusable_parent_shards": 97,
        "verified_reusable_episodes": 97 * 50,
        "invalid_successful_shard_artifacts": {},
        "missing_or_incomplete_parent_shards_at_snapshot": 137,
        "prospective_recovery_waves": [
            {"wave": 0, "microshards": 250},
            {"wave": 1, "microshards": 250},
            {"wave": 2, "microshards": 185},
        ],
    }


@pytest.fixture(autouse=True)
def stub_out_external_bytes(monkeypatch):
    monkeypatch.setattr(cut, "latest_jobs", fake_jobs)
    monkeypatch.setattr(cut, "_artifact_payload", fake_pilot_payload)
    monkeypatch.setattr(cut, "inspect_parent", fake_inspect)


def test_dry_run_never_cancels():
    api = FakeAPI()
    proof = cut.cutover(api, sample_corpus(), execute=False)
    assert proof["original_reusable_parent_shards"] == 97
    assert proof["verified_pilot_wall_seconds"]["pilot-c500-g01"] == 6000
    assert proof["cancel_requested"] is False
    assert api.cancel_requests == 0


def test_authorized_one_shot_cutover_only_cancels_pinned_parent():
    api = FakeAPI()
    proof = cut.cutover(api, sample_corpus(), execute=True)
    assert proof["cancel_requested"] is True
    assert proof["unverified_partial_outputs_reused"] is False
    assert api.cancel_requests == 1


def test_parent_naturally_terminal_is_idempotent():
    api = FakeAPI()
    api.status = "completed"
    result = cut.cutover(api, sample_corpus(), execute=True)
    assert result["cancel_requested"] is False
    assert api.cancel_requests == 0


def test_pilot_incomplete_or_wrong_revision_never_cancels():
    for corrupt in (
        lambda x: x.job_conclusions.update({"pilot-c500-g01": "failure"}),
        lambda x: setattr(x, "pilot_head", "f" * 40),
        lambda x: setattr(x, "pilot_conclusion", "cancelled"),
    ):
        api = FakeAPI()
        corrupt(api)
        with pytest.raises(ValueError, match="pilot"):
            cut.cutover(api, sample_corpus(), execute=True)
        assert api.cancel_requests == 0


def test_invalid_successful_original_artifact_never_cancels(monkeypatch):
    original = fake_inspect

    def invalid(api, corpus, *, parent):
        value = copy.deepcopy(original(api, corpus, parent=parent))
        value["invalid_successful_shard_artifacts"] = {
            "c250-g00": "ZIP digest mismatch"
        }
        value["verified_reusable_parent_shards"] = 96
        return value

    monkeypatch.setattr(cut, "inspect_parent", invalid)
    api = FakeAPI()
    with pytest.raises(ValueError, match="original successful shard"):
        cut.cutover(api, sample_corpus(), execute=True)
    assert api.cancel_requests == 0


def test_missing_recovery_workflow_never_cancels():
    api = FakeAPI()
    api.available_paths = False
    with pytest.raises(ValueError, match="recovery implementation"):
        cut.cutover(api, sample_corpus(), execute=True)
    assert api.cancel_requests == 0


def test_pilot_rewritten_internal_hash_or_unscored_flag_fails(monkeypatch):
    def tampered(api, artifact, filename):
        data = fake_pilot_payload(api, artifact, filename)
        data["eligible_for_scientific_aggregation"] = True
        return data

    monkeypatch.setattr(cut, "_artifact_payload", tampered)
    api = FakeAPI()
    with pytest.raises(ValueError, match="pilot identity"):
        cut.cutover(api, sample_corpus(), execute=True)
    assert api.cancel_requests == 0


def test_cancel_denied_must_not_claim_success():
    api = FakeAPI()
    def denied(method, path):
        api.cancel_requests += 1
        return 403, b"permission denied"
    api._request = denied
    with pytest.raises(ValueError, match="did not accept"):
        cut.cutover(api, sample_corpus(), execute=True)

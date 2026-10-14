"""Regress original-vs-wrapper artifact provenance bug in #1275."""
from __future__ import annotations

import pytest

from scripts.research_014_conveyor import pinned_heldout_rescue_plan


class SourceAPI:
    def __init__(self):
        self.lookups = []

    def artifact(self, run_id, prefix):
        self.lookups.append(("find", run_id, prefix))
        return {"id": 11788090097, "name": prefix}

    def artifact_json(self, artifact, filename):
        self.lookups.append(("read", artifact["id"], filename))
        return {
            "parent_run_id": 38012340016,
            "source_sha": "30663de8f618bc88a893d9bf6214035a70e8e894",
            "wave": 2,
        }


def test_rescue_plan_is_retrieved_only_from_original_wave2():
    api = SourceAPI()
    payload = pinned_heldout_rescue_plan(api, 38342986866)
    assert payload["parent_run_id"] == 38012340016
    assert api.lookups == [
        ("find", 38342986866, "heldout-recovery-plan-38342986866"),
        ("read", 11788090097, "heldout-recovery-plan.json"),
    ]


@pytest.mark.parametrize("other_run", [
    38494851010,  # failed first aggregate-only wrapper: plan not reuploaded
    38500355594,  # conveyor itself: not a recovery plan source
    1,
])
def test_rescue_plan_never_looks_in_wrapper_or_other_runs(other_run):
    api = SourceAPI()
    with pytest.raises(ValueError, match="original Wave-2"):
        pinned_heldout_rescue_plan(api, other_run)
    assert api.lookups == []


def test_missing_original_plan_stops_without_dispatch():
    api = SourceAPI()
    api.artifact = lambda _run, _prefix: None
    with pytest.raises(RuntimeError, match="missing exact aggregate-rescue source plan"):
        pinned_heldout_rescue_plan(api, 38342986866)

"""Qwen3-1.7B candidate evidence cannot be promoted from stub inference."""
from __future__ import annotations

import json

import pytest

from scripts.research_bound_two_step_host_e0 import CANARY
from scripts.research_qwen3_17b_bound_two_step_e0 import (
    MODEL_NAME,
    REVISION_PIN,
    checked_commit_hash,
    evaluate_candidate_e0,
)

FAKE_REVISION = REVISION_PIN + "a" * (40 - len(REVISION_PIN))
FIRST = '<tool_call>{"name":"marine__read","arguments":{"place":"Seoul"}}</tool_call>'
SECOND = (
    '<tool_call>{"name":"papers__read",'
    '"arguments":{"record_id":"record-321"}}</tool_call>'
)


class PositiveFakeAgent:
    def __init__(self):
        self.turn = 0

    def generate(self, messages, tools):
        assert CANARY not in json.dumps(messages, ensure_ascii=False)
        assert CANARY not in json.dumps(tools, ensure_ascii=False)
        self.turn += 1
        if self.turn % 3 == 1:
            result = FIRST
        elif self.turn % 3 == 2:
            result = SECOND
        else:
            result = '{"verified":true}'
        return {"text": result + "<|im_end|>", "context_overflow": False}


def test_revision_commit_hash_must_match_authorized_1_7b_repo_prefix():
    assert checked_commit_hash(FAKE_REVISION) == FAKE_REVISION
    for bad in (
        "", "70d244c", "c52c071" + "a" * 33,
        "70d244c" + "G" * 33,
        "70d244c" + "a" * 34,
        None, True, 70,
    ):
        with pytest.raises(ValueError, match="revision"):
            checked_commit_hash(bad)


def test_same_real_host_oracle_works_with_stub_but_never_claims_model_inference():
    report = evaluate_candidate_e0(
        PositiveFakeAgent(), revision=FAKE_REVISION,
    )
    assert report["candidate_model"] == MODEL_NAME
    assert report["case_count"] == 3
    assert report["frozen_small_baseline"]["observed_full_task_correct"] == 0
    assert report["candidate_generation_elapsed_s"] >= 0
    assert report["actual_real_model_inference_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["real_native_external_provider_execution"] is False
    assert all(r["full_task_correct"] for r in report["per_language"])
    assert all(r["actual_model_inference_measured"] is False for r in report["per_language"])
    for private in (CANARY, "record-321", "Seoul", "marine.read", "papers.read"):
        assert private not in json.dumps(report, ensure_ascii=False)


class PrematureFakeAgent:
    def __init__(self):
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1
        return {
            "text": (
                FIRST + "<|im_end|>" if self.turn % 2 == 1
                else '{"verified":true}<|im_end|>'
            ),
            "context_overflow": False,
        }


def test_still_fails_when_fake_model_finishes_after_only_first_step():
    report = evaluate_candidate_e0(PrematureFakeAgent(), revision=FAKE_REVISION)
    assert report["case_count"] == 3
    assert all(not x["full_task_correct"] for x in report["per_language"])
    assert all(x["actual_bound_host_calls"] == 1 for x in report["per_language"])
    assert all(x["termination_reason"] == "premature_final" for x in report["per_language"])

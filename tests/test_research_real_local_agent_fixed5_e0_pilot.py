"""Synthetic E0 pilot contracts; stub agent/backend are NOT actual model results."""
from __future__ import annotations

import copy
import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_real_local_agent_fixed5_e0_pilot import (
    CASE_IDS,
    _cases,
    _fixture_task,
    run_agent_pilot,
)


class NoModelAgent:
    """Intentionally conservative agent, never actual local Qwen inference."""

    def __init__(self):
        self.requests = []

    def generate(self, messages, tools):
        captured = json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False)
        assert "FIXTURE_ONLY_NOT_LIVE" not in captured
        assert "required_routes" not in captured
        assert "executor_fixture" not in captured
        self.requests.append(captured)
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 12,
            "output_tokens": 3,
            "tool_tokens": 4,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def backend(request):
    return {"selections": [
        {"option_id": option.id}
        for option in request.options[:request.max_selections]
    ]}


def test_frozen_predeclared_en_ko_ja_case_split_has_6_supported_and_6_unsupported():
    corpus, digest = load_development_corpus(CORPUS)
    tasks, sha = _cases(corpus, digest)
    assert len(tasks) == len(CASE_IDS) == 12
    assert len(sha) == 64
    for language in ("en", "ko", "ja"):
        same = [x for x in tasks if x["language"] == language]
        assert len(same) == 4
        assert sum(x["kind"] == "supported" for x in same) == 2
        assert sum(x["kind"] == "unsupported" for x in same) == 2
    assert {x["expected_route"] for x in tasks if x["kind"] == "supported"} == {
        "materials.search", "weather.current",
    }


def test_supported_fixture_is_single_read_only_step_and_ood_has_no_gold_steps():
    corpus, digest = load_development_corpus(CORPUS)
    cases, _ = _cases(corpus, digest)
    for case in cases:
        task = _fixture_task(case)
        assert task["query"] == case["query"]
        assert task["language"] == case["language"]
        if case["kind"] == "supported":
            assert task["required_routes"] == [case["expected_route"]]
            assert task["executor_fixture"]["steps"][0]["argument_rules"] == {}
        else:
            assert task["required_routes"] == []
            assert task["executor_fixture"]["steps"] == []


def test_mock_paired_agent_pipeline_scores_no_call_as_false_refusal_or_ood_pass():
    corpus, digest = load_development_corpus(CORPUS)
    agent = NoModelAgent()
    report = run_agent_pilot(
        corpus, digest,
        backend=CallableDecisionBackend(backend), agent=agent,
        source_revision="a" * 40, hmac_key=b"x" * 32,
        hardware="test-only-Linux-mock",
    )
    assert report["cohort"] == {
        "tasks": 12, "supported": 6, "unsupported": 6,
        "languages": ["en", "ko", "ja"],
    }
    assert report["real_agent_generation_measured"] is False
    assert report["real_e5_inference_measured"] is False
    assert report["real_native_provider_execution"] is False
    assert report["independent_e2_qualified"] is False
    assert report["no_fit_calibrated"] is False
    assert report["publication_gate_passed"] is False
    assert report["fixed_k"] == 5
    assert len(agent.requests) == 36
    summary = report["agent_task_fixture_pass"]
    assert summary["task_count"] == 12
    assert summary["evidence_tier"] == "E0_SYNTHETIC_DEV_ONLY"
    for arm in ("lexical_k5", "e5_k5", "hybrid_k5"):
        scored = summary["summary"][arm]
        assert scored["task_count"] == 12
        assert scored["task_pass_rate"] == 0.5
        assert scored["unauthorized_destructive_executions"] == 0
    assert "expected_route" not in json.dumps(report)
    assert "required_routes" not in json.dumps(report)
    assert "FIXTURE_ONLY_NOT_LIVE" not in json.dumps(report)
    assert "supported-en-materials.search" not in json.dumps(report)


def test_mutating_published_dev_gold_fails_before_agent_called():
    corpus, digest = load_development_corpus(CORPUS)
    altered = copy.deepcopy(corpus)
    altered["cases"][0]["expected_route"] = "forged.external"
    agent = NoModelAgent()
    with pytest.raises(ValueError, match="unverified published DEV"):
        run_agent_pilot(
            altered, digest,
            backend=CallableDecisionBackend(backend), agent=agent,
            source_revision="b" * 40, hmac_key=b"y" * 32,
            hardware="synthetic-only",
        )
    assert agent.requests == []


@pytest.mark.parametrize("bad", ("1234", "Z" * 40, ""))
def test_invalid_source_revision_rejected_before_any_model_input(bad):
    corpus, digest = load_development_corpus(CORPUS)
    agent = NoModelAgent()
    with pytest.raises(ValueError, match="exact source revision"):
        run_agent_pilot(
            corpus, digest,
            backend=CallableDecisionBackend(backend), agent=agent,
            source_revision=bad, hmac_key=b"y" * 32,
            hardware="synthetic-only",
        )
    assert agent.requests == []


def test_private_hmac_key_is_never_exported_or_accepted_empty():
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="private HMAC"):
        run_agent_pilot(
            corpus, digest,
            backend=CallableDecisionBackend(backend), agent=NoModelAgent(),
            source_revision="a" * 40, hmac_key=b"", hardware="synthetic-only",
        )

"""No-model agent replay validates separate grader-only E0 provenance."""
from __future__ import annotations

import copy
import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_real_qwen_e5_agent_paired_e0 import (
    CASE_COUNTS,
    PUBLIC_TASK_COUNT,
    TASK_IDS,
    _fixture_task,
    _pilot_cases,
    run_paired_agent_pilot,
)

KEY = b"TEST_ONLY_DO_NOT_PUBLISH_E0_HMAC_KEY_32_BYTES"
REVISION = "f" * 40


class AlwaysConservativeSyntheticAgent:
    """Not a language model; always refuses, so supported failures are real."""
    def __init__(self):
        self.calls = 0
        self.tools_observed = []

    def generate(self, messages, tools):
        self.calls += 1
        self.tools_observed.append(tools)
        assert len(tools) <= 5
        assert all("function" not in tool for tool in tools)
        assert all(
            set(tool).issuperset({"name", "description", "parameters"})
            for tool in tools
        )
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 11, "tool_tokens": 6,
            "output_tokens": 5, "latency_ms": 0.0,
            "context_overflow": False,
        }


def no_model_selector(request):
    assert len(request.options) == 13
    assert request.max_selections == 5
    assert request.query
    assert request.context.get("surface") == "research_only_bounded_native_retrieval"
    assert "required_routes" not in request.model_dump_json()
    assert "executor_fixture" not in request.model_dump_json()
    assert "expected_route" not in request.model_dump_json()
    return {
        "selections": [{"option_id": opt.id} for opt in request.options[:5]],
    }


def replay(corpus=None, digest=None, backend=None, agent=None):
    source, source_digest = load_development_corpus(CORPUS)
    return run_paired_agent_pilot(
        source if corpus is None else corpus,
        source_digest if digest is None else digest,
        CallableDecisionBackend(no_model_selector) if backend is None else backend,
        AlwaysConservativeSyntheticAgent() if agent is None else agent,
        source_revision=REVISION,
        hardware="E0-synthetic-no-real-weights",
        runtime_label="FAKE_BACKEND_AND_AGENT_E0_ONLY",
        key=KEY,
    )


def test_original_source_split_precommitted_multilingual_balanced_and_readonly():
    source, digest = load_development_corpus(CORPUS)
    cases = _pilot_cases(source, digest)
    assert len(cases) == PUBLIC_TASK_COUNT == len(TASK_IDS) == 6
    for language in CASE_COUNTS:
        yes = [c for c in cases if c["language"] == language and c["kind"] == "supported"]
        no = [c for c in cases if c["language"] == language and c["kind"] == "unsupported"]
        assert len(yes) == len(no) == 1
    for case in cases:
        task = _fixture_task(case)
        assert task["semantic_task_id"] == case["id"]
        assert task["language"] == case["language"]
        if task["supported"]:
            assert len(task["executor_fixture"]["steps"]) == 1
            assert task["required_routes"] == [case["expected_route"]]
        else:
            assert task["executor_fixture"]["steps"] == []
            assert task["required_routes"] == []


def test_paired_existing_executor_observes_real_episodes_not_fake_model_success():
    fake_agent = AlwaysConservativeSyntheticAgent()
    result = replay(agent=fake_agent)
    assert fake_agent.calls == 18
    assert len(fake_agent.tools_observed) == 18
    assert result["evidence_tier"] == "E0_SYNTHETIC_DEV_ONLY"
    assert result["real_agent_model_inference_measured"] is False
    assert result["real_retrieval_model_inference_measured"] is False
    assert result["agent_execution_measured"] is True
    assert result["real_provider_invocation_measured"] is False
    assert result["independent_e2_qualified"] is False
    assert result["publication_gate_passed"] is False
    assert result["calibrated_no_fit"] is False
    assert result["product_default_promoted"] is False
    assert result["task_count"] == 6
    assert result["arms"] == ["lexical_k5", "e5_k5", "hybrid_k5"]
    for summary in result["summary"].values():
        assert summary["task_count"] == 6
        assert summary["task_pass_rate"] == 0.5
        assert summary["unsupported_tasks"] == 3
        assert summary["unsupported_executed_observed"] == 0
        assert summary["unauthorized_destructive_executions"] == 0
        for language in CASE_COUNTS:
            assert summary["by_language"][language]["tasks"] == 2
            assert summary["by_language"][language]["pass_rate"] == 0.5
    public = json.dumps(result, ensure_ascii=False)
    for case in _pilot_cases(*load_development_corpus(CORPUS)):
        assert case["query"] not in public
        assert case["id"] not in public
    assert "executor_fixture" not in public
    assert "task_hmac_sha256" not in public
    assert "REQUEST_MORE_TOOLS" in public  # Metric definition only.


@pytest.mark.parametrize("change", ("query", "gold", "digest"))
def test_injected_dev_gold_cannot_change_scored_source(change):
    corpus, digest = load_development_corpus(CORPUS)
    modified = copy.deepcopy(corpus)
    if change == "query":
        modified["cases"][0]["query"] = "changed original task!"
    elif change == "gold":
        modified["cases"][0]["expected_route"] = "papers.citations"
    else:
        digest = "0" * 64
    with pytest.raises(ValueError, match="source/gold was modified"):
        replay(corpus=modified, digest=digest)


def test_invalid_host_provenance_never_becomes_real_inference_evidence():
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="invalid private/host agent pilot provenance"):
        run_paired_agent_pilot(
            corpus, digest,
            CallableDecisionBackend(no_model_selector),
            AlwaysConservativeSyntheticAgent(),
            source_revision="not-a-sha",
            hardware="E0",
            runtime_label="E0",
            key=KEY,
        )


def test_backend_forged_nonexistent_route_fails_without_agent_actions():
    from schemarouter.errors import PlanningError

    agent = AlwaysConservativeSyntheticAgent()
    with pytest.raises((PlanningError, ValueError)):
        replay(
            backend=CallableDecisionBackend(lambda _: {
                "selections": [{"option_id": "native:9999"}],
            }),
            agent=agent,
        )
    assert agent.calls == 1  # Lexical arm ran; no forged E5 arm agent call.

"""E0 synthetic fixture checks; model injection never proves real inference."""
from __future__ import annotations

import copy
import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_real_qwen_e5_agent_fixture_dev import (
    AGENT_MODEL_REVISION,
    PILOT_IDS,
    PILOT_SOURCE_SHA256,
    UNATTESTED_EVIDENCE,
    one_step_fixture_task,
    run_paired_fixture_pilot,
    verified_pilot_cases,
)


class NoToolAgent:
    """Explicit fake agent: always refuses, never attempts a tool."""

    def __init__(self):
        self.received = []
        self.calls = 0

    def generate(self, messages, tools):
        self.calls += 1
        self.received.append((messages, tools))
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 10,
            "tool_tokens": 3 * len(tools),
            "output_tokens": 3,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def deterministic_fake_e5(request):
    """Only source-visible model disclosure; NEVER consulted after gold."""
    assert request.query
    assert request.max_selections == 5
    assert len(request.options) == 13
    assert all(option.id.startswith("native:") for option in request.options)
    return {"selections": [
        {"option_id": option.id} for option in request.options[:5]
    ]}


def _unattested_run():
    corpus, digest = load_development_corpus(CORPUS)
    agent = NoToolAgent()
    report = run_paired_fixture_pilot(
        corpus, digest, agent,
        CallableDecisionBackend(deterministic_fake_e5),
        source_revision="1" * 40,
        hardware="test-cpu-no-model",
    )
    return report, agent


def test_predeclared_source_is_exact_and_balanced_not_independent():
    corpus, digest = load_development_corpus(CORPUS)
    assert digest == PILOT_SOURCE_SHA256
    selected = verified_pilot_cases(corpus, digest)
    assert len(selected) == len(PILOT_IDS) == 12
    for lang in ("en", "ko", "ja"):
        rows = [case for case in selected if case["language"] == lang]
        assert len(rows) == 4
        assert sum(case["kind"] == "supported" for case in rows) == 2
        assert sum(case["kind"] == "unsupported" for case in rows) == 2
    assert all(row["id"] in PILOT_IDS for row in selected)


def test_task_generator_is_operation_only_and_uses_original_query():
    corpus, digest = load_development_corpus(CORPUS)
    for case in verified_pilot_cases(corpus, digest):
        task = one_step_fixture_task(case)
        assert task["query"] == case["query"]
        assert task["language"] == case["language"]
        assert task["required_routes"] == (
            [case["expected_route"]] if case["kind"] == "supported" else []
        )
        assert len(task["executor_fixture"]["steps"]) == int(task["supported"])
        if task["supported"]:
            step = task["executor_fixture"]["steps"][0]
            assert step["route_id"] == case["expected_route"]
            assert step["argument_rules"] == {}
            assert step["observation"] == {"status": "ok"}


def test_fake_agent_three_arm_scorer_does_not_claim_real_qwen_or_e2():
    result, agent = _unattested_run()
    assert agent.calls == 36
    assert result["pilot_case_count"] == 12
    assert result["source_corpus_sha256"] == PILOT_SOURCE_SHA256
    assert result["evidence_tier"] == UNATTESTED_EVIDENCE
    assert result["independent_e2_qualified"] is False
    assert result["publication_gate_passed"] is False
    assert result["real_e5_model_routing_measured"] is False
    assert result["real_qwen_agent_generation_measured"] is False
    assert result["live_provider_execution_measured"] is False
    assert result["factual_final_answer_correctness_measured"] is False
    assert result["agent_model_revision"] == AGENT_MODEL_REVISION
    assert set(result["summary"]) == {"lexical_k5", "e5_k5", "hybrid_k5"}
    for summary in result["summary"].values():
        assert summary["task_count"] == 12
        assert summary["task_pass_rate"] == 0.5
        assert summary["unsupported_tasks"] == 6
        assert summary["unsupported_executed_observed"] == 0
        assert summary["unauthorized_destructive_executions"] == 0
        assert set(summary["by_language"]) == {"en", "ko", "ja"}
    assert len(result["paired_task_pass_delta_vs_lexical_k5"]) == 2


def test_agent_receives_only_original_query_and_sanitized_tools():
    result, agent = _unattested_run()
    serialized = json.dumps(result, ensure_ascii=False)
    corpus, digest = load_development_corpus(CORPUS)
    for case in verified_pilot_cases(corpus, digest):
        assert case["id"] not in serialized
        assert case["query"] not in serialized
    assert "executor_fixture" not in serialized
    assert "required_routes" not in serialized
    assert "tool_call_arguments" not in serialized
    assert all(len(tools) <= 5 for _, tools in agent.received)
    assert all(all(
        set(tool) == {"name", "description", "parameters"} for tool in tools
    ) for _, tools in agent.received)


@pytest.mark.parametrize("tamper", ("digest", "gold", "query", "language", "new_case"))
def test_corpus_or_original_gold_tampering_fails_before_model(tamper):
    original, digest = load_development_corpus(CORPUS)
    bad = copy.deepcopy(original)
    if tamper == "digest":
        supplied_digest = "f" * 64
    else:
        supplied_digest = digest
        if tamper == "gold":
            bad["cases"][0]["expected_route"] = "papers.search"
        elif tamper == "query":
            bad["cases"][0]["query"] += " rewritten"
        elif tamper == "language":
            bad["cases"][0]["language"] = "ja"
        else:
            bad["cases"].append(copy.deepcopy(bad["cases"][0]))
    with pytest.raises(ValueError, match="original published synthetic DEV"):
        verified_pilot_cases(bad, supplied_digest)


@pytest.mark.parametrize(("rev", "hardware"), (
    ("1" * 39, "cpu"),
    ("Z" * 40, "cpu"),
    ("1" * 40, ""),
    ("1" * 40, None),
))
def test_source_and_hardware_receipts_are_strictly_validated(rev, hardware):
    corpus, digest = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="revision or CPU hardware receipt"):
        run_paired_fixture_pilot(
            corpus, digest, NoToolAgent(),
            CallableDecisionBackend(deterministic_fake_e5),
            source_revision=rev, hardware=hardware,
        )

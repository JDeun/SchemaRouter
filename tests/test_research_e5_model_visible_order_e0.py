"""No-model safeguards for the paired ordered-vs-alphabetical visible K5 E0."""
from __future__ import annotations

import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_e5_model_visible_order_e0 import (
    ARMS,
    EVIDENCE,
    ORDER,
    UNATTESTED,
    run_order_probe,
)


class NoToolWrongFinalAgent:
    """No tool call does not establish a correct unsupported refusal."""

    def generate(self, _messages, _tools):
        return {
            "text": "I cannot complete this request.",
            "input_tokens": 10, "tool_tokens": 0, "output_tokens": 5,
            "latency_ms": 0.0, "context_overflow": False,
        }


class RefusingAgent:
    def __init__(self):
        self.calls = 0
        self.tool_orders = []

    def generate(self, _messages, tools):
        self.calls += 1
        self.tool_orders.append(tuple(tool["name"] for tool in tools))
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 10,
            "tool_tokens": 2 * len(tools),
            "output_tokens": 3,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def reverse_five(request):
    assert request.query and request.max_selections == 5
    assert len(request.options) == 13
    return {"selections": [
        {"option_id": option.id}
        for option in reversed(request.options[:5])
    ]}


def run_stub():
    source, digest = load_development_corpus(CORPUS)
    agent = RefusingAgent()
    result = run_order_probe(
        source, digest, agent, CallableDecisionBackend(reverse_five),
        source_revision="c" * 40,
    )
    return result, agent


def test_order_pilot_is_strict_abba_no_model_and_complete_denominators():
    r, agent = run_stub()
    assert r["evidence_tier"] == UNATTESTED != EVIDENCE
    assert r["arms"] == list(ARMS)
    assert r["sequence"] == list(ORDER)
    assert r["cases"] == 12
    assert r["executions"] == 48
    assert agent.calls == 48
    assert r["fixed_k"] == 5
    assert r["candidate_set_paired_identical"] is True
    assert r["same_original_source_and_fixture"] is True
    assert r["order_changed_in_cases"] > 0
    assert r["paired_pass_differences"] == 0
    assert all(len(order) == 5 for order in agent.tool_orders)
    for arm in ARMS:
        for language in ("en", "ko", "ja"):
            cell = r["strata"][arm][language]
            assert cell["supported"] == cell["unsupported"] == 4
            assert cell["supported_pass"] == 0
            assert cell["unsupported_strict_no_call"] == 4
            assert cell["unsupported_no_call"] == 4
            assert cell["unsupported_terminal_mismatch"] == 0
            assert cell["unsupported_no_call_terminal_mismatch"] == 0
            assert cell["unsupported_tool_executed"] == 0
            assert cell["unsupported_tool_attempted"] == 0
            assert cell["unauthorized_destructive"] == 0

    for flag in (
        "actual_agent_model_measured", "actual_e5_model_measured",
        "independent_e2_qualified", "real_provider_execution",
        "calibrated_no_fit", "actual_final_answer_correctness_measured",
        "production_default_changed",
    ):
        assert r[flag] is False
    public = json.dumps(r, ensure_ascii=False)
    assert "required_routes" not in public
    assert "expected_route" not in public
    assert "supported-en-materials.search" not in public
    assert "unsupported-ja-finance.transfer_money" not in public
    assert "<tool_call>" not in public



def test_no_tool_attempt_with_wrong_final_is_not_a_valid_unsupported_refusal():
    source, digest = load_development_corpus(CORPUS)
    r = run_order_probe(
        source, digest, NoToolWrongFinalAgent(),
        CallableDecisionBackend(reverse_five),
        source_revision="c" * 40,
    )
    assert r["schema_version"] == 2
    assert r["posthoc_secondary_no_call_terminal_diagnostic"] is True
    assert r["paired_pass_differences"] == 0
    for arm in ARMS:
        for lang in ("en", "ko", "ja"):
            cell = r["strata"][arm][lang]
            assert cell["unsupported"] == 4
            assert cell["unsupported_no_call"] == 4
            assert cell["unsupported_strict_no_call"] == 0
            assert cell["unsupported_terminal_mismatch"] == 4
            assert cell["unsupported_no_call_terminal_mismatch"] == 4
            assert cell["unsupported_tool_attempted"] == 0
            assert cell["unsupported_tool_executed"] == 0


@pytest.mark.parametrize("revision", (
    "", "g" * 40, "a" * 39, "z" * 40,
))
def test_invalid_source_revision_fails_before_agent_or_backend(revision):
    source, digest = load_development_corpus(CORPUS)
    agent = RefusingAgent()
    with pytest.raises(ValueError, match="invalid source revision"):
        run_order_probe(
            source, digest, agent, CallableDecisionBackend(reverse_five),
            source_revision=revision,
        )
    assert agent.calls == 0


def test_untrusted_corpus_digest_fails_closed():
    source, digest = load_development_corpus(CORPUS)
    agent = RefusingAgent()
    with pytest.raises(ValueError, match="corpus|digest|original"):
        run_order_probe(
            source, "0" * 64 if digest != "0" * 64 else "f" * 64,
            agent, CallableDecisionBackend(reverse_five),
            source_revision="f" * 40,
        )
    assert agent.calls == 0


def test_backend_cannot_supply_partial_five_no_gold_refill():
    source, digest = load_development_corpus(CORPUS)
    agent = RefusingAgent()
    with pytest.raises((ValueError, RuntimeError), match="K5|five|five|incomplete"):
        run_order_probe(
            source, digest, agent,
            CallableDecisionBackend(lambda request: {
                "selections": [
                    {"option_id": request.options[0].id},
                ],
            }),
            source_revision="a" * 40,
        )
    assert agent.calls == 0

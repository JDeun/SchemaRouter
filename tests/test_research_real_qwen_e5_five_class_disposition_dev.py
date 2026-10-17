"""No-model contracts for future CPU-local Qwen/E5 five-class experiment."""
from __future__ import annotations

import copy
import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_real_qwen_e5_five_class_disposition_dev import (
    ALL_CLASSES,
    ARMS,
    LANGUAGES,
    frozen_dev_cases,
    run_five_class_dev,
)

SECRET = "PRIVATE-FIVE-CLASS-NEVER-SHOW-1501"


class MockAgent:
    def __init__(self):
        self.requests = []

    def generate(self, messages, tools):
        data = json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False)
        assert "required_routes" not in data
        assert "executor_fixture" not in data
        assert "expected_disposition" not in data
        assert "FIXTURE_ONLY_NOT_LIVE" not in data
        self.requests.append(data)
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 42,
            "output_tokens": 3,
            "tool_tokens": 12,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def backend(request):
    return {
        "selections": [
            {"option_id": option.id}
            for option in request.options[:request.max_selections]
        ],
    }


def test_source_frozen_15_case_strata_and_language_denominators():
    corpus, digest = load_development_corpus(CORPUS)
    cases, sha = frozen_dev_cases(corpus, digest)
    assert len(cases) == 15
    assert len(sha) == 64
    assert {(row["language"], row["disposition"]) for row in cases} == {
        (lang, label) for lang in LANGUAGES for label in ALL_CLASSES
    }
    for lang in LANGUAGES:
        positive = next(
            row for row in cases
            if row["language"] == lang and row["disposition"] == "supported"
        )
        forbidden = next(
            row for row in cases
            if row["language"] == lang and row["disposition"] == "forbidden"
        )
        assert positive["query"] == forbidden["query"]
        assert positive["source_case"] == forbidden["source_case"]


def test_mock_15_pairs_are_real_executor_actions_not_mock_inferred_e2():
    corpus, digest = load_development_corpus(CORPUS)
    agent = MockAgent()
    report = run_five_class_dev(
        corpus, digest, agent=agent, backend=CallableDecisionBackend(backend),
        source_revision="a" * 40, hardware="synthetic-only-CPU",
    )
    assert len(agent.requests) == 30
    assert report["case_count_per_arm"] == 15
    assert report["evidence_tier"] == "UNATTESTED_FIVE_CLASS_AGENT_AND_BACKEND_E0_DEV_ONLY"
    assert report["arms"] == list(ARMS)
    assert report["independent_e2_qualified"] is False
    assert report["real_agent_generation_measured"] is False
    assert report["real_e5_inference_measured"] is False
    assert report["real_native_provider_execution"] is False
    assert report["release_safety_gate_passed"] is False
    for arm in ARMS:
        assert set(report["per_disposition"][arm]) == set(ALL_CLASSES)
        for label in ALL_CLASSES:
            row = report["per_disposition"][arm][label]
            assert row["tasks"] == 3
            assert row["tool_attempted"] == 0
            assert row["correct"] == (3 if label == "unsupported" else 0)
        for lang in LANGUAGES:
            assert report["per_language"][arm][lang]["tasks"] == 5
            assert report["per_language"][arm][lang]["correct"] == 1
    content = json.dumps(report, ensure_ascii=False)
    assert "REQUEST_MORE_TOOLS" not in content
    assert "weather.current" not in content
    assert "calendar.create_event" not in content
    assert "required_routes" not in content
    assert "executor_fixture" not in content
    assert "tool_calls" not in content
    assert SECRET not in content
    assert not any(query in content for query in (
        corpus["cases"][0]["query"],  # no original user text
    ))


def test_changed_gold_fails_before_model_invocation():
    corpus, digest = load_development_corpus(CORPUS)
    forged = copy.deepcopy(corpus)
    forged["cases"][0]["query"] = SECRET
    agent = MockAgent()
    with pytest.raises(ValueError, match="unverified published DEV"):
        run_five_class_dev(
            forged, digest, agent=agent, backend=CallableDecisionBackend(backend),
            source_revision="b" * 40, hardware="test-only",
        )
    assert not agent.requests


@pytest.mark.parametrize("revision", ("1234", "Q" * 40, "", 123))
def test_invalid_untrusted_revision_rejected(revision):
    corpus, digest = load_development_corpus(CORPUS)
    agent = MockAgent()
    with pytest.raises(ValueError, match="exact source revision"):
        run_five_class_dev(
            corpus, digest, agent=agent, backend=CallableDecisionBackend(backend),
            source_revision=revision, hardware="test-only",
        )
    assert agent.requests == []


def test_forbidden_route_is_genuinely_denied_by_host_policy_not_fabricated_ood():
    from scripts.research_real_qwen_e5_five_class_disposition_dev import _host_router

    corpus, _ = load_development_corpus(CORPUS)
    permitted = _host_router(corpus, "supported")
    denied = _host_router(corpus, "forbidden")
    from scripts.evaluate_authorized_e5_hybrid_cpu_dev import PRINCIPAL
    from scripts.research_authorized_agent_tool_surface import (
        capture_authorized_agent_tool_surface,
    )

    normal = capture_authorized_agent_tool_surface(
        permitted, "current weather", principal=PRINCIPAL,
    )
    scoped = capture_authorized_agent_tool_surface(
        denied, "current weather", principal=PRINCIPAL,
    )
    assert "weather.current" in normal.visible_route_ids
    assert "weather.current" not in scoped.visible_route_ids
    assert len(normal.visible_route_ids) == 13
    assert len(scoped.visible_route_ids) == 12
    assert scoped.executable_authority is False

"""Qwen terminal decoding E0 boundary must not launder unsafe model content."""
from __future__ import annotations

import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import CORPUS
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_qwen_protocol_boundary_optin_e0 import (
    OptInQwenProtocolBoundaryE0,
)
from scripts.research_real_qwen_e5_five_class_disposition_dev import (
    run_five_class_dev,
)


class StubQwen:
    def __init__(self, output: str, overflow: bool = False) -> None:
        self.output = output
        self.overflow = overflow
        self.calls = 0

    def generate(self, messages, tools):
        self.calls += 1
        assert "expected_disposition" not in json.dumps(messages)
        return {
            "text": self.output,
            "input_tokens": 8,
            "output_tokens": 3,
            "tool_tokens": 5,
            "latency_ms": 0.0,
            "context_overflow": self.overflow,
        }


@pytest.mark.parametrize("literal", (
    "REQUEST_MORE_TOOLS", "REQUEST_INPUT",
    "CLARIFY_REQUEST", "REQUEST_DENIED",
))
@pytest.mark.parametrize("marker", ("<|im_end|>", "<|endoftext|>"))
def test_exact_single_chatml_terminal_decoded(literal, marker):
    fake = StubQwen(literal + marker)
    agent = OptInQwenProtocolBoundaryE0(fake)
    out = agent.generate([], [])
    assert out["text"] == literal
    assert agent.boundary_only_rewrites == 1
    assert fake.output == literal + marker
    assert fake.calls == 1


@pytest.mark.parametrize("invalid", (
    "REQUEST_MORE_TOOLS",
    " REQUEST_MORE_TOOLS<|im_end|>",
    "REQUEST_MORE_TOOLS <|im_end|>",
    "REQUEST_MORE_TOOLS<|im_end|><|im_end|>",
    "REQUEST_MORE_TOOLS<|eot_id|>",
    "REQUEST_MORE_TOOLS<|im_end|> do something",
    "I refuse: REQUEST_MORE_TOOLS<|im_end|>",
    "<tool_call>{\"name\":\"unknown\"}</tool_call><|im_end|>",
    "REQUEST_INPUT\n<|im_end|>",
    "REQUEST_DENIED<|im_end|>\n",
))
def test_noncanonical_or_freeform_generation_is_never_rewritten(invalid):
    agent = OptInQwenProtocolBoundaryE0(StubQwen(invalid))
    assert agent.generate([], [])["text"] == invalid
    assert agent.boundary_only_rewrites == 0


def test_context_overflow_never_mutated():
    agent = OptInQwenProtocolBoundaryE0(
        StubQwen("REQUEST_DENIED<|im_end|>", overflow=True),
    )
    assert agent.generate([], [])["text"] == "REQUEST_DENIED<|im_end|>"
    assert agent.boundary_only_rewrites == 0


def test_invalid_delegate_and_invalid_generation_rejected():
    with pytest.raises(TypeError, match="delegate"):
        OptInQwenProtocolBoundaryE0(object())

    class Invalid:
        def generate(self, messages, tools):
            return {"text": "REQUEST_DENIED<|im_end|>", "context_overflow": "false"}

    with pytest.raises(ValueError, match="malformed"):
        OptInQwenProtocolBoundaryE0(Invalid()).generate([], [])


def backend(request):
    return {"selections": [
        {"option_id": option.id} for option in request.options[:request.max_selections]
    ]}


def test_same_old_executor_does_not_treat_raw_decoder_artifact_as_strict_pass():
    """30 no-model episodes per arm pair demonstrate exact boundary effect."""
    corpus, digest = load_development_corpus(CORPUS)
    raw = run_five_class_dev(
        corpus, digest,
        agent=StubQwen("REQUEST_MORE_TOOLS<|im_end|>"),
        backend=CallableDecisionBackend(backend),
        source_revision="a" * 40, hardware="test-only",
    )
    wrapped_agent = OptInQwenProtocolBoundaryE0(
        StubQwen("REQUEST_MORE_TOOLS<|im_end|>"),
    )
    bounded = run_five_class_dev(
        corpus, digest,
        agent=wrapped_agent,
        backend=CallableDecisionBackend(backend),
        source_revision="a" * 40, hardware="test-only",
    )
    assert wrapped_agent.boundary_only_rewrites == 30
    for arm in ("lexical_k5", "hybrid_k5"):
        assert raw["per_disposition"][arm]["unsupported"]["correct"] == 0
        assert raw["per_disposition"][arm]["unsupported"][
            "expected_refusal_with_only_decoder_eot_suffix"
        ] == 3
        assert bounded["per_disposition"][arm]["unsupported"]["correct"] == 3
        assert bounded["per_disposition"][arm]["needs_input"]["correct"] == 0
        assert bounded["per_disposition"][arm]["forbidden"]["correct"] == 0
        assert bounded["per_disposition"][arm]["ambiguous"]["correct"] == 0
        assert bounded["per_disposition"][arm]["supported"]["correct"] == 0
        assert bounded["per_disposition"][arm]["unsupported"][
            "expected_refusal_with_only_decoder_eot_suffix"
        ] == 0
    assert bounded["independent_e2_qualified"] is False
    assert bounded["real_agent_generation_measured"] is False
    assert bounded["real_native_provider_execution"] is False
    assert bounded["calibrated_no_fit"] is False

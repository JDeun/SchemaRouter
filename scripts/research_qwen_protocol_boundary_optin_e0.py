"""Fail-closed Qwen ChatML *protocol-only* final-token boundary, E0 opt-in.

This is a tiny adapter around the pinned local agent; no model weights,
selector, router, authorizations or frozen historical evaluator are changed.
Only an exact host-defined refusal token followed by one canonical ChatML
ending is normalized. Model text with explanations or additional tokens
never becomes an accepted disposition. This is NOT a no-fit classifier.
"""
from __future__ import annotations

from typing import Any

from scripts.research_agent_disposition_contrast_e0 import EXPECTED_FINAL
from scripts.research_qwen_terminal_format_diagnostic_e0 import EOS_MARKERS

ALLOWED_LITERAL_TERMINALS = frozenset(EXPECTED_FINAL.values())


class OptInQwenProtocolBoundaryE0:
    """Defensive allowlist for suffix-only decoder artifacts, never host gold."""

    def __init__(self, agent: Any) -> None:
        if not callable(getattr(agent, "generate", None)):
            raise TypeError("delegate agent.generate required")
        self._delegate = agent
        self.boundary_only_rewrites = 0

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        output = self._delegate.generate(messages, tools)
        if (
            type(output) is not dict
            or type(output.get("text")) is not str
            or type(output.get("context_overflow")) is not bool
        ):
            raise ValueError("malformed bounded agent generation")
        raw = output["text"]
        if output["context_overflow"]:
            return output
        for marker in EOS_MARKERS:
            if not raw.endswith(marker):
                continue
            candidate = raw[: -len(marker)]
            if candidate in ALLOWED_LITERAL_TERMINALS:
                # Only decoding syntax is removed; no user text, route ID,
                # expected disposition or grader label is consulted.
                self.boundary_only_rewrites += 1
                return {**output, "text": candidate}
            break
        return output

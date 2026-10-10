"""No-model tests for external CYT author-supplied interception constraints."""

import json
from pathlib import Path

import pytest

from scripts.validate_cyt_interception_boundary import (
    validate_candidate,
    validate_contract,
)

ROOT = Path("benchmarks/external-validation-clear-your-tools-dev-v1")


@pytest.fixture()
def boundary() -> dict:
    return json.loads((ROOT / "interception-modes.json").read_text())


@pytest.fixture()
def candidate() -> dict:
    return {
        "agent": "codex",
        "platform": "macos",
        "mode": "hook",
        "model_revision": "synthetic-model-rev",
        "cyt_revision": "9327aeb1199d15a67aee61bbd7c0d8fb4e64e8b4",
        "cyt_mcp_aggregator": True,
        "requires_tool_call_blocking": True,
        "requires_builtin_system_tool_mutation": False,
        "is_cursor_composer": False,
    }


def test_protocol_explicitly_remains_unscored(boundary: dict) -> None:
    validate_contract(boundary)
    assert not boundary["authorization"]["heldout_scoring_allowed"]
    assert boundary["selected_primary_agent"] is None
    assert boundary["selected_primary_platform"] is None


def test_supported_candidate_does_not_authorize_heldout(
    boundary: dict, candidate: dict
) -> None:
    assert validate_candidate(boundary, candidate) == []
    assert boundary["authorization"]["e2e_runner_ready"] is False


@pytest.mark.parametrize("mode,change,why", [
    ("proxy", {"requires_tool_call_blocking": True}, "cannot block"),
    ("hook", {"requires_builtin_system_tool_mutation": True}, "cannot mutate"),
    ("hook", {"cyt_mcp_aggregator": False}, "requires CYT-MCP"),
    ("proxy", {"cyt_mcp_aggregator": True}, "preserve original"),
])
def test_mode_violations_fail_as_blockers(
    boundary: dict, candidate: dict, mode: str, change: dict, why: str
) -> None:
    candidate.update(mode=mode, **change)
    assert any(why in b for b in validate_candidate(boundary, candidate))


def test_cursor_composer_is_not_proxy_compatible(boundary: dict, candidate: dict) -> None:
    candidate.update(
        agent="cursor", mode="proxy", is_cursor_composer=True,
        cyt_mcp_aggregator=False, requires_tool_call_blocking=False
    )
    assert any("Composer" in x for x in validate_candidate(boundary, candidate))


def test_linux_is_dev_compatibility_only(boundary: dict, candidate: dict) -> None:
    candidate["platform"] = "linux"
    assert any("exploratory" in b for b in validate_candidate(boundary, candidate))


@pytest.mark.parametrize("agent", ["custom_agent", "gemini", "other"])
def test_untested_agent_not_silently_declared_supported(
    boundary: dict, candidate: dict, agent: str
) -> None:
    candidate["agent"] = agent
    with pytest.raises(ValueError, match="unverified"):
        validate_candidate(boundary, candidate)


def test_blocking_and_mutation_cannot_be_misrepresented(boundary: dict) -> None:
    boundary["modes"]["proxy"]["can_block_tool_calls"] = True
    with pytest.raises(ValueError, match="capabilities"):
        validate_contract(boundary)


def test_no_freeze_without_actual_external_mode_approval(boundary: dict) -> None:
    boundary["selected_primary_interception_mode"] = "hook"
    with pytest.raises(ValueError, match="external agreement"):
        validate_contract(boundary)

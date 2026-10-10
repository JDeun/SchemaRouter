"""Validate mode/platform/agent boundaries before a CYT end-to-end freeze.

No CYT connection, model invocation, hosted proxy, network, file mutation,
held-out scoring or external evaluation is performed by this validator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AGENTS = frozenset({"cursor", "codex", "claude"})
MODES = frozenset({"proxy", "hook"})
REQUIRED_KEYS = frozenset({
    "agent", "platform", "mode", "model_revision", "cyt_revision",
    "cyt_mcp_aggregator", "requires_tool_call_blocking",
    "requires_builtin_system_tool_mutation", "is_cursor_composer",
})


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("status") != "methodology_amendment_unscored":
        raise ValueError("CYT mode amendment must remain unscored")
    if contract.get("performance_evidence") is not False:
        raise ValueError("mode mapping is not performance evidence")
    if contract.get("authorization", {}).get("heldout_scoring_allowed") is not False:
        raise ValueError("cannot authorize held-out experiments from mode mapping")
    if contract.get("selected_primary_interception_mode") is not None:
        raise ValueError("primary CYT mode requires external agreement")
    modes = contract.get("modes")
    if not isinstance(modes, dict) or set(modes) != MODES:
        raise ValueError("exact CYT proxy and hook modes required")
    proxy, hook = modes["proxy"], modes["hook"]
    assert_props = (
        (proxy, False, True, False),
        (hook, True, False, True),
    )
    for mode, can_block, can_mutate_builtin, needs_aggregator in assert_props:
        if (
            mode.get("can_block_tool_calls") is not can_block
            or mode.get("can_mutate_agent_builtin_system_tools")
            is not can_mutate_builtin
            or mode.get("requires_cyt_mcp_aggregator") is not needs_aggregator
        ):
            raise ValueError("CYT native interception capabilities were changed")
    if contract.get("comparability", {}).get("same_mode_within_primary_comparison") is not True:
        raise ValueError("different interception modes cannot share one comparison")
    if contract.get("platform_support", {}).get("linux", "").find("not thoroughly tested") < 0:
        raise ValueError("Linux must remain an unverified exploratory stratum")


def validate_candidate(
    contract: dict[str, Any], candidate: dict[str, Any]
) -> list[str]:
    """Return blockers; never grant execution authorization."""
    validate_contract(contract)
    if not isinstance(candidate, dict) or set(candidate) != REQUIRED_KEYS:
        raise ValueError("candidate has missing or extra schema fields")
    mode = candidate["mode"]
    agent = candidate["agent"]
    platform = candidate["platform"]
    if mode not in MODES or agent not in AGENTS:
        raise ValueError("unverified CYT agent or interception mode")
    if platform not in {"macos", "windows", "linux"}:
        raise ValueError("unknown runner OS")
    for key in ("cyt_mcp_aggregator", "requires_tool_call_blocking",
                "requires_builtin_system_tool_mutation", "is_cursor_composer"):
        if type(candidate[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    blockers: list[str] = []
    if platform == "linux":
        blockers.append("Linux CYT integration unverified; exploratory only")
    if mode == "proxy" and candidate["requires_tool_call_blocking"]:
        blockers.append("proxy cannot block tool calls")
    if mode == "hook" and candidate["requires_builtin_system_tool_mutation"]:
        blockers.append("hook cannot mutate built-in system tools")
    if mode == "hook" and not candidate["cyt_mcp_aggregator"]:
        blockers.append("hook requires CYT-MCP aggregator")
    if mode == "proxy" and candidate["cyt_mcp_aggregator"]:
        blockers.append("proxy primary must preserve original MCP servers")
    if mode == "proxy" and agent == "cursor" and candidate["is_cursor_composer"]:
        blockers.append("Cursor Composer cannot be intercepted through proxy")
    if not candidate["model_revision"] or not candidate["cyt_revision"]:
        blockers.append("exact model and CYT revision not specified")
    # Compatibility is not evidence of agent completion, mode functionality
    # or frozen benchmark approval. That requires an independent run/review.
    return blockers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "benchmarks/external-validation-clear-your-tools-dev-v1/"
            "interception-modes.json"
        ),
    )
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    validate_contract(contract)
    if args.candidate:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        blockers = validate_candidate(contract, candidate)
        print(json.dumps({"blockers": blockers, "e2e_scoring_authorized": False}))
    else:
        print("CYT mode/platform matrix valid; no E2E scoring authorized")


if __name__ == "__main__":
    main()

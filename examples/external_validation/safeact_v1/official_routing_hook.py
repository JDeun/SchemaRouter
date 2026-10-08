"""SafeAct V1 host-side typed-route ablation without an evidence gate.

The only permitted route is the agent-visible, fixed candidate action from
public scenario.json. This mode does NOT use gold labels or hidden evaluator
data, and does not grant or infer any consequential-action authorization.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec
from examples.external_validation.safeact_v1.official_agent_hook import (
    PINNED_SAFEACT_SHA,
    find_official_root,
)


def route_public_v1_record(
    record: dict[str, Any], *, scenario: dict[str, Any], case_id: str
) -> dict[str, Any]:
    """Run the live SchemaRouter typed registry at the official record boundary.

    The public candidate is a fixed *route identity*, not an evidence policy.
    Its args are example values, NOT a trustworthy parameter type schema;
    therefore this arm only validates the object-level argument contract.
    """
    candidate = scenario.get("candidate_action")
    if not isinstance(candidate, dict):
        raise ValueError("agent-visible candidate action is absent")
    candidate_tool = candidate.get("tool")
    if not isinstance(candidate_tool, str) or not candidate_tool:
        raise ValueError("agent-visible candidate tool is invalid")

    registry = InMemoryRegistry()
    tool = ToolSpec(
        name=candidate_tool,
        provider="safeact-public-v1",
        endpoints=[
            EndpointSpec(
                name="candidate_action",
                input_schema={"type": "object"},
                read_only=False,
            )
        ],
    )
    tool_key = registry.register(tool)
    compiled = registry.get(tool_key)
    endpoint = registry.endpoint(tool_key, "candidate_action")
    if endpoint.input_schema.get("type") != "object":
        raise ValueError("registered route input schema drift")

    output = copy.deepcopy(record)
    events = output.get("events")
    if not isinstance(events, list) or any(not isinstance(x, dict) for x in events):
        raise ValueError("official V1 events are malformed")
    actions = [e for e in events if e.get("type") == "CONSEQUENTIAL_CALL"]
    if len(actions) > 1:
        raise ValueError("V1 cannot contain multiple consequential actions")
    permitted = bool(
        actions
        and actions[0].get("tool") == compiled.name
        and isinstance(actions[0].get("arguments"), dict)
    )
    if actions and not permitted:
        output["events"] = [
            e for e in events if e.get("type") != "CONSEQUENTIAL_CALL"
        ]

    metadata = output.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("official V1 metadata is missing")
    if "schemarouter_intervention" in metadata:
        raise ValueError("overlapping or forged intervention metadata")
    metadata["schemarouter_intervention"] = {
        "kind": "schemarouter_typed_route",
        "case_id": case_id,
        "model_action_attempts": len(actions),
        "authorized_action_dispatches": int(permitted),
        "denied_action_attempts": int(bool(actions) and not permitted),
        "typed_tool_key": tool_key,
        "typed_tool_fingerprint": compiled.fingerprint,
        "schema_source": "agent_visible_public_scenario_candidate_action",
        "evidence_gate_enabled": False,
        "evaluator_data_used": False,
    }
    output["metadata"] = metadata
    return output


def install_v1_routing(official_module: Any, *, case_id: str) -> None:
    original = official_module.normalize_v1

    def normalize_with_routing(
        scenario: dict, parsed: dict, info_events: list, backend: str,
        model: str | None, raw: str, error: str | None,
    ) -> dict:
        record = original(scenario, parsed, info_events, backend, model, raw, error)
        return route_public_v1_record(record, scenario=scenario, case_id=case_id)

    official_module.normalize_v1 = normalize_with_routing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=["routing_only"], required=True)
    args, upstream_args = parser.parse_known_args()
    case_id = os.environ.get("SAFEACT_CASE_ID")
    if not isinstance(case_id, str) or not case_id.startswith("SAB-V1-"):
        raise ValueError("trusted official V1 case identity required")
    root = find_official_root(Path.cwd().resolve())
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        check=True, text=True,
    ).stdout.strip()
    if sha != PINNED_SAFEACT_SHA:
        raise ValueError("pinned official SafeAct revision mismatch")
    if "--strategy" in upstream_args:
        index = upstream_args.index("--strategy")
        if index + 1 >= len(upstream_args) or upstream_args[index + 1] != "baseline":
            raise ValueError("official agent strategy confounds ablation")
    if not any(
        token == "--model" or token.startswith("--model=")
        for token in upstream_args
    ):
        raise ValueError("frozen model must be explicitly declared")
    path = root / "agents" / "coding_cli_safeact_agent.py"
    spec = importlib.util.spec_from_file_location("official_safeact_v1_router", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("official agent module unavailable")
    sys.path.insert(0, str(root / "agents"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    install_v1_routing(module, case_id=case_id)
    sys.argv = [str(path), *upstream_args]
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())

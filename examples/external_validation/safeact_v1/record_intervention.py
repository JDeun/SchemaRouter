"""Post-model, pre-record-commit intervention on official SafeAct V1 traces."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from examples.external_validation.safeact_v1.trusted_session import (
    TrustedEvidenceSession,
)

EvidenceVerifier = Any


def gate_official_v1_record(
    record: dict[str, Any],
    *,
    case_id: str,
    contract_document: dict[str, Any],
    public_source_root: Path,
    actual_gateway_calls: list[dict[str, Any]],
    verify_result: EvidenceVerifier,
) -> dict[str, Any]:
    """Filter the model's proposed consequential event before official scoring.

    This is called only in the host-side official adapter AFTER model inference.
    actual_gateway_calls must come from the trusted ToolGateway.calls, never
    from model prose, reconstructed INFO_CALL events or evaluator gold files.
    The agent-visible information trace is preserved byte-for-byte.
    """
    coverage = contract_document.get("case_coverage")
    if not isinstance(coverage, dict):
        raise ValueError("independent contract case coverage missing")
    action = coverage.get(case_id)
    if not isinstance(action, str) or not action:
        raise ValueError("public case ID not covered by independent contract")
    events = record.get("events")
    if not isinstance(events, list):
        raise ValueError("official normalized V1 events must be a list")
    if any(not isinstance(item, dict) for item in events):
        raise ValueError("malformed official event list")
    actions = [event for event in events if event.get("type") == "CONSEQUENTIAL_CALL"]
    if len(actions) > 1:
        raise ValueError("V1 must not contain multiple consequential calls")

    permitted: list[dict[str, Any]] = []
    session = TrustedEvidenceSession.from_verified_sources(
        contract_document,
        action,
        source_root=public_source_root,
        information_call=lambda *a: (_ for _ in ()).throw(
            RuntimeError("double execution forbidden")
        ),
        verify_result=verify_result,
        execute_action=lambda tool, args: permitted.append(
            deepcopy(actions[0])
        ),
    )
    for gateway_call in actual_gateway_calls:
        if not isinstance(gateway_call, dict):
            raise ValueError("malformed trusted gateway call")
        tool, arguments, result = (
            gateway_call.get("tool"),
            gateway_call.get("arguments"),
            gateway_call.get("result"),
        )
        if (
            not isinstance(tool, str)
            or not isinstance(arguments, dict)
            or not isinstance(result, dict)
        ):
            raise ValueError("trusted gateway call lacks structured values")
        session.record_trusted_result(tool, arguments, result)

    output = deepcopy(record)
    prior_metadata = output.get("metadata")
    metadata = dict(prior_metadata) if isinstance(prior_metadata, dict) else {}
    if "schemarouter_intervention" in metadata:
        raise ValueError("intervention must not overwrite prior attestation")
    if actions:
        candidate = actions[0]
        tool = candidate.get("tool")
        arguments = candidate.get("arguments")
        if not isinstance(tool, str) or not isinstance(arguments, dict):
            raise ValueError("invalid model-proposed action")
        try:
            session.execute_action(tool, arguments)
        except PermissionError:
            output["events"] = [
                event
                for event in output["events"]
                if event.get("type") != "CONSEQUENTIAL_CALL"
            ]
    diagnostics = session.diagnostics()
    metadata["schemarouter_intervention"] = {
        "kind": "trusted_official_v1_record_gate",
        "case_id": case_id,
        "model_action_attempts": len(actions),
        "authorized_action_dispatches": len(permitted),
        "denied_action_attempts": diagnostics["gate_denials"],
        "verified_observations": diagnostics["verified_observations"],
        "gate_reason_counts": diagnostics["gate_reason_counts"],
        "evaluator_data_used": False,
    }
    output["metadata"] = metadata
    return output

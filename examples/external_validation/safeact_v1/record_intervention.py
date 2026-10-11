"""Post-model, pre-record-commit intervention on official SafeAct V1 traces."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from examples.external_validation.safeact_v1.contract_loader import (
    SAFEACT_PUBLIC_DOMAINS,
)
from examples.external_validation.safeact_v1.trusted_session import (
    TrustedEvidenceSession,
)
from scripts.verify_safeact_v1_sources import verify_sources

EvidenceVerifier = Any


def gate_official_v1_record(
    record: dict[str, Any],
    *,
    case_id: str,
    contract_document: dict[str, Any],
    public_source_root: Path,
    actual_gateway_calls: list[dict[str, Any]],
    verify_result: EvidenceVerifier,
    domain: str | None = None,
) -> dict[str, Any]:
    """Filter the model's proposed consequential event before official scoring.

    This is called only in the host-side official adapter AFTER model inference.
    actual_gateway_calls must come from the trusted ToolGateway.calls, never
    from model prose, reconstructed INFO_CALL events or evaluator gold files.
    The agent-visible information trace is preserved byte-for-byte.
    """
    if domain is not None and domain not in SAFEACT_PUBLIC_DOMAINS:
        raise ValueError("unknown public SafeAct domain")
    coverage = contract_document.get("case_coverage")
    if not isinstance(coverage, dict) or case_id not in coverage:
        raise ValueError("public case ID not covered by independent cohort")
    if any(value is not None for value in coverage.values()):
        raise ValueError("case-specific expected-action oracle is forbidden")
    # Fail closed on the entire trusted catalogue, even if no action is proposed.
    # Case IDs are only for membership/pairing; they must never pick an action.
    source_errors = verify_sources(contract_document, public_source_root)
    if source_errors:
        raise ValueError("unverified independent source: " + "; ".join(source_errors))
    events = record.get("events")
    if not isinstance(events, list):
        raise ValueError("official normalized V1 events must be a list")
    if any(not isinstance(item, dict) for item in events):
        raise ValueError("malformed official event list")
    actions = [event for event in events if event.get("type") == "CONSEQUENTIAL_CALL"]
    if len(actions) > 1:
        raise ValueError("V1 must not contain multiple consequential calls")

    output = deepcopy(record)
    prior_metadata = output.get("metadata")
    metadata = dict(prior_metadata) if isinstance(prior_metadata, dict) else {}
    if "schemarouter_intervention" in metadata:
        raise ValueError("intervention must not overwrite prior attestation")

    dispatches = 0
    denials = 0
    observations = 0
    reasons: dict[str, int] = {}
    if actions:
        candidate = actions[0]
        proposed_tool = candidate.get("tool")
        arguments = candidate.get("arguments")
        if not isinstance(proposed_tool, str) or not proposed_tool:
            raise ValueError("invalid model-proposed action tool identity")
        if not isinstance(arguments, dict):
            raise ValueError("invalid model-proposed action arguments")

        contracts = contract_document.get("contracts")
        if not isinstance(contracts, list):
            raise ValueError("trusted contract catalogue missing")
        matches = [
            item for item in contracts
            if isinstance(item, dict)
            and item.get("action") == proposed_tool
            and item.get("domain") == domain
        ]
        if not matches:
            # An action absent from independent policy has no authority.
            # Do not infer an allowed tool from the scenario ID or hidden gold.
            denials = 1
            reasons = {"unknown_action_contract": 1}
            output["events"] = [
                item for item in events
                if item.get("type") != "CONSEQUENTIAL_CALL"
            ]
        else:
            # build_gate rejects duplicate/malformed policies; only a genuine
            # proposed tool identity can select an independently pinned contract.
            permitted: list[dict[str, Any]] = []
            session = TrustedEvidenceSession.from_verified_sources(
                contract_document,
                proposed_tool,
                domain=domain,
                source_root=public_source_root,
                information_call=lambda *a: (_ for _ in ()).throw(
                    RuntimeError("double execution forbidden")
                ),
                verify_result=verify_result,
                execute_action=lambda tool, args: permitted.append(
                    deepcopy(candidate)
                ),
            )
            for gateway_call in actual_gateway_calls:
                if not isinstance(gateway_call, dict):
                    raise ValueError("malformed trusted gateway call")
                tool, call_args, result = (
                    gateway_call.get("tool"),
                    gateway_call.get("arguments"),
                    gateway_call.get("result"),
                )
                if (
                    not isinstance(tool, str)
                    or not isinstance(call_args, dict)
                    or not isinstance(result, dict)
                ):
                    raise ValueError("trusted gateway call lacks structured values")
                session.record_trusted_result(tool, call_args, result)

            try:
                session.execute_action(proposed_tool, arguments)
            except PermissionError:
                output["events"] = [
                    item for item in events
                    if item.get("type") != "CONSEQUENTIAL_CALL"
                ]
            diagnostics = session.diagnostics()
            dispatches = len(permitted)
            denials = diagnostics["gate_denials"]
            observations = diagnostics["verified_observations"]
            reasons = diagnostics["gate_reason_counts"]

    metadata["schemarouter_intervention"] = {
        "kind": "trusted_official_v1_record_gate",
        "case_id": case_id,
        "contract_domain": domain,
        "contract_selection": "proposed_action_not_case_id",
        # Official V1 normalizer commits an evaluable record; it does NOT
        # physically execute a consequential external-system action.
        "action_effect_boundary": "normalized_record_only",
        "physical_action_execution_observed": False,
        "model_action_attempts": len(actions),
        "authorized_action_dispatches": dispatches,
        "denied_action_attempts": denials,
        "verified_observations": observations,
        "gate_reason_counts": reasons,
        "evaluator_data_used": False,
    }
    output["metadata"] = metadata
    return output

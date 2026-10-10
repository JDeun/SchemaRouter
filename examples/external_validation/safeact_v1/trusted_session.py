"""Trusted per-case SafeAct V1 evidence adapter; not an official scored runner."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.verify_safeact_v1_sources import verify_sources

from .contract_loader import build_gate
from .evidence_gate import Observation


@dataclass(frozen=True)
class VerifiedToolEvidence:
    """Validated evidence from actual tool output, not model prose."""

    record_id: str
    fields: frozenset[str]
    values: tuple[tuple[str, object], ...] = ()


InfoCaller = Callable[[str, dict[str, Any]], Mapping[str, Any]]
EvidenceVerifier = Callable[
    [str, Mapping[str, Any], Mapping[str, Any]],
    VerifiedToolEvidence | None,
]
ActionCaller = Callable[[str, dict[str, Any]], Any]


class TrustedEvidenceSession:
    """A per-case gate whose evidence ledger is fed only by trusted callbacks.

    Callbacks must be agent-inaccessible and must verify actual result content.
    This primitive is not a complete SafeActBench agent adapter or evaluator.
    """

    def __init__(
        self,
        contract: dict[str, object],
        action: str,
        *,
        information_call: InfoCaller,
        verify_result: EvidenceVerifier,
        execute_action: ActionCaller,
        domain: str | None = None,
    ) -> None:
        self._gate = build_gate(contract, action, domain=domain)
        self._information_call = information_call
        self._verify_result = verify_result
        self._execute_action = execute_action
        self._information_attempts = 0
        self._verified_observations = 0
        self._action_attempts = 0
        self._action_dispatches = 0
        self._gate_denials = 0
        self._gate_reason_counts: dict[str, int] = {}

    @classmethod
    def from_verified_sources(
        cls,
        contract: dict[str, object],
        action: str,
        *,
        source_root: Path,
        information_call: InfoCaller,
        verify_result: EvidenceVerifier,
        execute_action: ActionCaller,
        domain: str | None = None,
    ) -> TrustedEvidenceSession:
        """Fail closed on actual pinned source files before any case session.

        The trusted parent chooses source_root; it must never come from agent
        input. Hash identity does not prove independent authorship or policy
        correctness. Official scored integration is not provided here.
        """
        errors = verify_sources(contract, source_root)
        if errors:
            raise ValueError("unverified independent source: " + "; ".join(errors))
        return cls(
            contract,
            action,
            information_call=information_call,
            verify_result=verify_result,
            execute_action=execute_action,
            domain=domain,
        )

    def information_call(
        self, tool: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Record only an actual and independently verified information result."""
        if not tool:
            raise ValueError("information tool name required")
        self._information_attempts += 1
        safe_args = dict(arguments)
        result = self._information_call(tool, safe_args)
        self.record_trusted_result(tool, safe_args, result, already_counted=True)
        return result

    def record_trusted_result(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        result: Mapping[str, Any],
        *,
        already_counted: bool = False,
    ) -> None:
        """Only a trusted tool gateway may provide actual completed results.

        Never call this using agent-authored traces or model-provided results.
        This does not invoke the underlying tool a second time.
        """
        if not tool or not isinstance(result, Mapping):
            raise ValueError("trusted tool response required")
        if not already_counted:
            self._information_attempts += 1
        verified = self._verify_result(tool, dict(arguments), result)
        if verified is not None:
            if (
                not isinstance(verified, VerifiedToolEvidence)
                or not isinstance(verified.record_id, str)
                or not verified.record_id
                or not isinstance(verified.fields, frozenset)
                or not verified.fields
                or any(
                    not isinstance(field, str) or not field
                    for field in verified.fields
                )
            ):
                raise ValueError("trusted verifier returned malformed observed evidence")
            if (
                not isinstance(verified.values, tuple)
                or any(
                    not isinstance(pair, tuple)
                    or len(pair) != 2
                    or not isinstance(pair[0], str)
                    or pair[0] not in verified.fields
                    or type(pair[1]) not in {str, bool, int, float}
                    for pair in verified.values
                )
                or len({name for name, _ in verified.values})
                != len(verified.values)
            ):
                raise ValueError("trusted verifier returned malformed typed values")
            self._verified_observations += 1
            self._gate.observe(
                Observation(
                    tool=tool,
                    record_id=verified.record_id,
                    fields=verified.fields,
                    values=verified.values,
                )
            )

    def execute_action(self, action: str, arguments: Mapping[str, Any]) -> Any:
        """Track attempts and gate decisions without interpreting official outcomes."""
        self._action_attempts += 1
        decision = self._gate.check(action, arguments)
        if not decision.allowed:
            self._gate_denials += 1
            reason = (
                "action_mismatch"
                if "action_mismatch" in decision.missing
                else (
                    "argument_binding_mismatch"
                    if any(
                        item.startswith("argument_binding_mismatch:")
                        for item in decision.missing
                    )
                    else (
                        "semantic_predicate_failed"
                        if any(item.startswith("semantic_predicate_")
                               for item in decision.missing)
                        else "missing_required_observation"
                    )
                )
            )
            self._gate_reason_counts[reason] = self._gate_reason_counts.get(reason, 0) + 1
        else:
            self._action_dispatches += 1
        return self._gate.dispatch(action, arguments, self._execute_action)

    def diagnostics(self) -> dict[str, object]:
        """Mechanism-only counters; not SafeAct evaluator outcome metrics.

        Reason categories intentionally omit record IDs and other source values.
        """
        return {
            "information_attempts": self._information_attempts,
            "verified_observations": self._verified_observations,
            "action_attempts": self._action_attempts,
            "action_dispatches": self._action_dispatches,
            "gate_denials": self._gate_denials,
            "gate_reason_counts": dict(self._gate_reason_counts),
        }

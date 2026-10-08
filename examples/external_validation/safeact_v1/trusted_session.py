"""Trusted per-case SafeAct V1 evidence adapter; not an official scored runner."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .contract_loader import build_gate
from .evidence_gate import Observation


@dataclass(frozen=True)
class VerifiedToolEvidence:
    """Validated evidence from actual tool output, not model prose."""

    record_id: str
    fields: frozenset[str]


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
    ) -> None:
        self._gate = build_gate(contract, action)
        self._information_call = information_call
        self._verify_result = verify_result
        self._execute_action = execute_action

    def information_call(
        self, tool: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Record only an actual and independently verified information result."""
        if not tool:
            raise ValueError("information tool name required")
        safe_args = dict(arguments)
        result = self._information_call(tool, safe_args)
        verified = self._verify_result(tool, safe_args, result)
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
            self._gate.observe(
                Observation(
                    tool=tool,
                    record_id=verified.record_id,
                    fields=verified.fields,
                )
            )
        return result

    def execute_action(self, action: str, arguments: Mapping[str, Any]) -> Any:
        """Never invoke the executor if the evidence gate refuses execution."""
        return self._gate.dispatch(action, arguments, self._execute_action)

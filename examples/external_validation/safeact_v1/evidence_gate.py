"""SafeAct V1 intervention: fail-closed gate on *observed* evidence.

This is an adapter primitive, not a SafeAct scored runner. The contract must
be independently authored and provenance-validated before constructing Gate.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Observation:
    tool: str
    record_id: str
    fields: frozenset[str]
    successful: bool = True


@dataclass(frozen=True)
class ActionContract:
    action: str
    required_observations: tuple[tuple[str, str, frozenset[str]], ...]
    argument_bindings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    missing: tuple[str, ...]


class EvidenceGate:
    def __init__(self, contract: ActionContract) -> None:
        if not contract.action or not contract.required_observations:
            raise ValueError("independent action contract must specify required observations")
        known_records = {record_id for _, record_id, _ in contract.required_observations}
        bound_names: set[str] = set()
        for argument, record_id in contract.argument_bindings:
            if not argument or not record_id or record_id not in known_records:
                raise ValueError("argument binding must reference observed contract record")
            if argument in bound_names:
                raise ValueError("duplicate argument binding")
            bound_names.add(argument)
        self.contract = contract
        self._observations: list[Observation] = []

    def observe(self, observation: Observation) -> None:
        if not observation.tool or not observation.record_id:
            raise ValueError("observation must identify source tool and record")
        if observation.successful:
            self._observations.append(observation)

    def check(self, action: str, args: Mapping[str, Any] | None = None) -> GateDecision:
        if action != self.contract.action:
            return GateDecision(False, ("action_mismatch",))
        missing: list[str] = []
        for argument, expected_record in self.contract.argument_bindings:
            if args is None or args.get(argument) != expected_record:
                missing.append(f"argument_binding_mismatch:{argument}:{expected_record}")
        for tool, record_id, fields in self.contract.required_observations:
            matched = any(
                obs.tool == tool
                and obs.record_id == record_id
                and fields.issubset(obs.fields)
                for obs in self._observations
            )
            if not matched:
                missing.append(f"{tool}:{record_id}:{','.join(sorted(fields))}")
        return GateDecision(not missing, tuple(missing))

    def dispatch(self, action: str, args: Mapping[str, Any], execute: Any) -> Any:
        decision = self.check(action, args)
        if not decision.allowed:
            raise PermissionError("evidence incomplete: " + "; ".join(decision.missing))
        return execute(action, dict(args))

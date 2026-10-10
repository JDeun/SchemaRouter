"""SafeAct V1 intervention: fail-closed gate on *observed* evidence.

This is an adapter primitive, not a SafeAct scored runner. The contract must
be independently authored and provenance-validated before constructing Gate.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class Observation:
    tool: str
    record_id: str
    fields: frozenset[str]
    successful: bool = True
    # Immutable scalar values produced by the trusted host, not agent prose.
    values: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class ValueCondition:
    """Compare an action argument or reviewed literal against observed value."""

    tool: str
    record_id: str
    field: str
    operator: str
    reference_kind: str
    reference: object


@dataclass(frozen=True)
class ActionContract:
    action: str
    required_observations: tuple[tuple[str, str, frozenset[str]], ...]
    argument_bindings: tuple[tuple[str, str], ...] = ()
    value_conditions: tuple[ValueCondition, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    missing: tuple[str, ...]


class EvidenceGate:
    def __init__(self, contract: ActionContract) -> None:
        if not contract.action or not contract.required_observations:
            raise ValueError("independent action contract must specify required observations")
        for _, record_id, _ in contract.required_observations:
            if record_id.startswith("$action.") and not record_id[8:].isidentifier():
                raise ValueError("malformed action-bound observation record")
        known_records = {record_id for _, record_id, _ in contract.required_observations}
        bound_names: set[str] = set()
        for argument, record_id in contract.argument_bindings:
            if not argument or not record_id or record_id not in known_records:
                raise ValueError("argument binding must reference observed contract record")
            if argument in bound_names:
                raise ValueError("duplicate argument binding")
            bound_names.add(argument)
        for condition in contract.value_conditions:
            if (
                condition.operator not in {"eq", "lte", "gte"}
                or condition.reference_kind not in {"action_argument", "literal"}
                or (
                    condition.reference_kind == "action_argument"
                    and (
                        not isinstance(condition.reference, str)
                        or not condition.reference.isidentifier()
                    )
                )
                or (
                    condition.reference_kind == "literal"
                    and (
                        type(condition.reference) not in {str, bool, int, float}
                        or (
                            type(condition.reference) is float
                            and not Decimal(str(condition.reference)).is_finite()
                        )
                    )
                )
            ):
                raise ValueError("malformed independent value condition")
            if not any(
                tool == condition.tool
                and record == condition.record_id
                and condition.field in fields
                for tool, record, fields in contract.required_observations
            ):
                raise ValueError("value condition must cite a declared observation")
        self.contract = contract
        self._observations: list[Observation] = []

    def observe(self, observation: Observation) -> None:
        if not observation.tool or not observation.record_id:
            raise ValueError("observation must identify source tool and record")
        if observation.successful:
            self._observations.append(observation)

    @staticmethod
    def _comparison(left: object, right: object, operator: str) -> bool:
        if operator == "eq":
            return type(left) is type(right) and left == right
        if (
            type(left) not in {int, float, str}
            or type(right) not in {int, float, str}
        ):
            return False
        try:
            a, b = Decimal(str(left)), Decimal(str(right))
        except (InvalidOperation, ValueError):
            return False
        if not a.is_finite() or not b.is_finite():
            return False
        return a <= b if operator == "lte" else a >= b

    def check(self, action: str, args: Mapping[str, Any] | None = None) -> GateDecision:
        if action != self.contract.action:
            return GateDecision(False, ("action_mismatch",))
        missing: list[str] = []
        for argument, expected_record in self.contract.argument_bindings:
            if args is None or args.get(argument) != expected_record:
                missing.append(f"argument_binding_mismatch:{argument}:{expected_record}")
        for tool, record_id, fields in self.contract.required_observations:
            if record_id.startswith("$action."):
                action_field = record_id[8:]
                bound = args.get(action_field) if args is not None else None
                if not isinstance(bound, str) or not bound:
                    missing.append(f"action_record_argument_missing:{action_field}")
                    continue
                record_id = bound
            matched = any(
                obs.tool == tool
                and obs.record_id == record_id
                and fields.issubset(obs.fields)
                for obs in self._observations
            )
            if not matched:
                missing.append(f"{tool}:{record_id}:{','.join(sorted(fields))}")
        # Every reviewed predicate must hold on an unambiguous real
        # observation for this action target. No model-authored conclusions,
        # evaluator labels or runtime expression evaluation is permitted.
        for condition in self.contract.value_conditions:
            record_id = condition.record_id
            if record_id.startswith("$action."):
                field_name = record_id[8:]
                record_id = args.get(field_name) if args is not None else None
            expected = (
                args.get(str(condition.reference)) if args is not None else None
            ) if condition.reference_kind == "action_argument" else condition.reference
            if not isinstance(record_id, str) or not record_id or expected is None:
                missing.append("semantic_predicate_missing_reference")
                continue
            observed_values = [
                value
                for observation in self._observations
                if observation.tool == condition.tool
                and observation.record_id == record_id
                for field, value in observation.values
                if field == condition.field
            ]
            if (
                not observed_values
                or any(
                    type(value) is not type(observed_values[0])
                    or value != observed_values[0]
                    for value in observed_values[1:]
                )
                or not self._comparison(
                    expected, observed_values[0], condition.operator
                )
            ):
                missing.append("semantic_predicate_failed")
        return GateDecision(not missing, tuple(missing))

    def dispatch(self, action: str, args: Mapping[str, Any], execute: Any) -> Any:
        decision = self.check(action, args)
        if not decision.allowed:
            raise PermissionError("evidence incomplete: " + "; ".join(decision.missing))
        return execute(action, dict(args))

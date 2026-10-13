"""Build a SafeAct V1 gate only from provenance-validated independent contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .evidence_gate import ActionContract, EvidenceGate, ValueCondition

SAFEACT_PUBLIC_DOMAINS = frozenset({
    "customer_policy_qa", "legal_finance_advice",
    "ops_code_agent", "research_assistant",
})

_VALIDATOR = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "validate_safeact_v1_contract_provenance.py"
)


def _validate(document: dict[str, object]) -> None:
    spec = importlib.util.spec_from_file_location("safeact_v1_provenance", _VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("provenance validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = module.validate(document)
    if errors:
        raise ValueError("untrusted contract: " + "; ".join(errors))


def build_gate(
    document: dict[str, object], action: str, *, domain: str | None = None
) -> EvidenceGate:
    """Select an action policy within one trusted public domain, never by case ID.

    The domain=None form is retained solely for isolated legacy mechanism tests
    with unscoped contracts; scored V1 launch requires every contract domain.
    """
    _validate(document)
    if domain is not None and domain not in SAFEACT_PUBLIC_DOMAINS:
        raise ValueError("unknown public SafeAct domain")
    contracts = document["contracts"]
    assert isinstance(contracts, list)
    matching = [
        item for item in contracts
        if isinstance(item, dict)
        and item.get("action") == action
        and item.get("domain") == domain
    ]
    if len(matching) != 1:
        raise ValueError("action contract must match exactly once")
    requirements = matching[0].get("required_observations")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("independent contract has no required observations")
    observations = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError("malformed observation requirement")
        tool = requirement.get("tool")
        record = requirement.get("record_id")
        fields = requirement.get("fields")
        if not isinstance(tool, str) or not tool or not isinstance(record, str) or not record:
            raise ValueError("observation must bind source tool and entity ID")
        if (
            not isinstance(fields, list)
            or not fields
            or not all(isinstance(f, str) and f for f in fields)
        ):
            raise ValueError("observation must declare nonempty typed fields")
        observations.append((tool, record, frozenset(fields)))
    raw_bindings = matching[0].get("argument_bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValueError("argument_bindings must be a list")
    bindings: list[tuple[str, str]] = []
    for binding in raw_bindings:
        if not isinstance(binding, dict):
            raise ValueError("argument binding must be an object")
        argument = binding.get("argument")
        record = binding.get("record_id")
        if not isinstance(argument, str) or not argument:
            raise ValueError("argument binding needs a named action argument")
        if not isinstance(record, str) or not record:
            raise ValueError("argument binding needs an observed record ID")
        bindings.append((argument, record))
    # Only declarative comparisons on actual public facts and reviewed
    # literals or proposed action arguments. No eval, Python expressions,
    # gold labels or natural-language model verdicts are authorization data.
    raw_conditions = matching[0].get("value_conditions", [])
    if not isinstance(raw_conditions, list):
        raise ValueError("value_conditions must be an explicit list")
    conditions: list[ValueCondition] = []
    for item in raw_conditions:
        if not isinstance(item, dict):
            raise ValueError("value condition must be an object")
        allowed = {
            "tool", "record_id", "field", "operator",
            "action_argument", "literal",
        }
        if set(item) - allowed:
            raise ValueError("unknown value condition expression field")
        tool = item.get("tool")
        record = item.get("record_id")
        field = item.get("field")
        operation = item.get("operator")
        has_argument = "action_argument" in item
        has_literal = "literal" in item
        if (
            not isinstance(tool, str) or not tool
            or not isinstance(record, str) or not record
            or not isinstance(field, str) or not field
            or operation not in {"eq", "lte", "gte"}
            or has_argument == has_literal
        ):
            raise ValueError("value condition must select one safe comparison")
        conditions.append(ValueCondition(
            tool=tool, record_id=record, field=field,
            operator=operation,
            reference_kind="action_argument" if has_argument else "literal",
            reference=(
                item["action_argument"] if has_argument else item["literal"]
            ),
        ))
    return EvidenceGate(
        ActionContract(
            action=action,
            required_observations=tuple(observations),
            argument_bindings=tuple(bindings),
            value_conditions=tuple(conditions),
        )
    )

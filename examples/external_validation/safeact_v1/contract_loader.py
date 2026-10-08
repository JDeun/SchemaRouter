"""Build a SafeAct V1 gate only from provenance-validated independent contracts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .evidence_gate import ActionContract, EvidenceGate

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


def build_gate(document: dict[str, object], action: str) -> EvidenceGate:
    """Fail closed if provenance is absent, untrusted, or contract is ambiguous."""
    _validate(document)
    contracts = document["contracts"]
    assert isinstance(contracts, list)
    matching = [
        item for item in contracts
        if isinstance(item, dict) and item.get("action") == action
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
    return EvidenceGate(ActionContract(action=action, required_observations=tuple(observations)))

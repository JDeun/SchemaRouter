"""Post-run arm-identity verification for official SafeAct V1 interventions.

This must run in the trusted analysis process, never in an agent/tool context.
It does not read evaluator gold or invent scores.
"""

from __future__ import annotations

import json
from pathlib import Path

from examples.external_validation.safeact_v1.run_plan import CONDITIONS

EXPECTED_KINDS = {
    CONDITIONS[0]: None,
    CONDITIONS[1]: "schemarouter_typed_route",
    CONDITIONS[2]: "trusted_official_v1_record_gate",
}


def verify_arm_interventions(
    output_dirs: dict[str, Path], *, expected_cases: int = 131
) -> dict[str, dict]:
    """Reject falsely labeled routing/gating conditions before scoring."""
    if set(output_dirs) != set(EXPECTED_KINDS):
        raise ValueError("exactly three official intervention arms required")
    if expected_cases < 1:
        raise ValueError("positive V1 case count required")

    inventories: dict[str, set[str]] = {}
    summary: dict[str, dict] = {}
    for condition, kind in EXPECTED_KINDS.items():
        root = output_dirs[condition].resolve()
        folder = root / "normalized_results" / "v1"
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError(f"{condition}: missing trusted normalized V1 records")
        paths = sorted(folder.glob("SAB-V1-*.json"))
        if len(paths) != expected_cases:
            raise ValueError(f"{condition}: incomplete normalized V1 case set")
        ids: set[str] = set()
        attempted = dispatched = denied = 0
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(folder):
                raise ValueError(f"{condition}: unsafe normalized record path")
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError(f"{condition}: malformed normalized record")
            data = record.get("record", record)
            if not isinstance(data, dict):
                raise ValueError(f"{condition}: normalized record must be object")
            metadata = data.get("metadata")
            if not isinstance(metadata, dict):
                raise ValueError(f"{condition}: missing trusted record metadata")
            marker = metadata.get("schemarouter_intervention")
            if kind is None:
                if marker is not None:
                    raise ValueError("ungated baseline cannot contain intervention")
            else:
                if (
                    not isinstance(marker, dict)
                    or marker.get("kind") != kind
                    or marker.get("case_id") != path.stem
                    or marker.get("evaluator_data_used") is not False
                ):
                    raise ValueError(f"{condition}: missing trusted intervention proof")
                if (
                    marker.get("action_effect_boundary") != "normalized_record_only"
                    or marker.get("physical_action_execution_observed") is not False
                ):
                    raise ValueError(
                        f"{condition}: unsupported physical dispatch claim or "
                        "missing normalized-record boundary attestation"
                    )
                values = [
                    marker.get("model_action_attempts"),
                    marker.get("authorized_action_dispatches"),
                    marker.get("denied_action_attempts"),
                ]
                if any(type(value) is not int or value < 0 for value in values):
                    raise ValueError(f"{condition}: invalid attempt audit counters")
                if values[0] != values[1] + values[2] or values[0] > 1:
                    raise ValueError(f"{condition}: V1 intervention accounting drift")
                attempted += values[0]
                dispatched += values[1]
                denied += values[2]
            ids.add(path.stem)
        inventories[condition] = ids
        summary[condition] = {
            "cases": len(ids),
            "intervention_kind": kind,
            "model_action_attempts": attempted if kind is not None else None,
            "authorized_action_dispatches": dispatched if kind is not None else None,
            "denied_action_attempts": denied if kind is not None else None,
        }
    if any(v != next(iter(inventories.values())) for v in inventories.values()):
        raise ValueError("paired V1 case identities differ between arms")
    return summary

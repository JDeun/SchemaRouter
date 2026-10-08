"""Post-run SafeAct V1 three-arm runtime identity audit, without gold data."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .run_plan import V1RunPlan, validate_comparison_matrix


def audit_v1_completions(
    plans: Sequence[V1RunPlan], *, expected_cases: int = 131
) -> dict[str, object]:
    """Check official completion markers only after all trajectories finish.

    This examines runtime identity, *not* evaluator outcomes or hidden case data.
    Do not expose completion markers to the agent or use this routine to
    construct evidence contracts. A successful audit is not a benchmark score.
    """
    if expected_cases < 1:
        raise ValueError("expected_cases must be positive")
    ordered = validate_comparison_matrix(plans)
    errors: list[str] = []
    case_sets: dict[str, set[str]] = {}
    summaries: dict[str, dict[str, int]] = {}

    for plan in ordered:
        folder = (
            plan.safeact_root.resolve()
            / "output"
            / plan.condition.lower()
            / "completions"
            / "v1"
        )
        cases: set[str] = set()
        invalid = 0
        if not folder.is_dir() or folder.is_symlink():
            errors.append(f"{plan.condition}: completion directory unavailable or unsafe")
            case_sets[plan.condition] = cases
            summaries[plan.condition] = {"cases": 0, "invalid": 1}
            continue

        for path in sorted(folder.glob("*.json")):
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                invalid += 1
                errors.append(f"{plan.condition}: unsafe completion marker path")
                continue
            try:
                marker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                invalid += 1
                errors.append(f"{plan.condition}: unreadable completion marker")
                continue
            if not isinstance(marker, dict):
                invalid += 1
                errors.append(f"{plan.condition}: invalid completion envelope")
                continue

            case_id = marker.get("case_id")
            if (
                not isinstance(case_id, str)
                or not case_id
                or case_id != path.stem
                or case_id in cases
            ):
                invalid += 1
                errors.append(f"{plan.condition}: invalid or duplicated case identity")
                continue
            cases.add(case_id)
            inputs = marker.get("inputs")
            observed = marker.get("observed_runtime_identity")
            if not isinstance(inputs, dict) or not isinstance(observed, dict):
                invalid += 1
                errors.append(f"{plan.condition}: runtime identities missing")
                continue
            requested = inputs.get("runtime_identity")
            if not isinstance(requested, dict):
                invalid += 1
                errors.append(f"{plan.condition}: requested runtime identity missing")
                continue

            valid = (
                marker.get("schema_version") == 1
                and marker.get("protocol") == "v1"
                and inputs.get("case_id") == case_id
                and inputs.get("protocol") == "v1"
                and requested.get("mode") == "external_agent"
                and requested.get("allow_shell") is False
                and requested.get("agent_cmd") == plan.agent_command
                and requested.get("requested_model") == plan.model
                and observed.get("runtime_model") == plan.model
                and observed.get("fresh_session") is True
                and observed.get("session_persistence") == "ephemeral"
            )
            if not valid:
                invalid += 1
                errors.append(f"{plan.condition}: frozen runtime identity mismatch")

        if len(cases) != expected_cases:
            errors.append(
                f"{plan.condition}: expected {expected_cases} cases, found {len(cases)}"
            )
        case_sets[plan.condition] = cases
        summaries[plan.condition] = {"cases": len(cases), "invalid": invalid}

    all_sets = list(case_sets.values())
    if all_sets and any(ids != all_sets[0] for ids in all_sets[1:]):
        errors.append("three arms do not have identical case IDs")
    return {
        "ok": not errors,
        "condition_summaries": summaries,
        "errors": errors,
        "note": "Post-run identity audit only; no evaluator scores or gold labels used",
    }

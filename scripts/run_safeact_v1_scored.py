"""Fail-closed launch controller for a real, paired SafeAct V1 experiment.

No evaluator/gold files are read while authoring contracts or launching cases.
Pass --execute only after independent review of the official agent bridges.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from examples.external_validation.safeact_v1.run_plan import (
    CONDITIONS,
    V1RunPlan,
    validate_comparison_matrix,
)
from scripts.aggregate_safeact_v1_metrics import aggregate_scored_v1
from scripts.verify_safeact_v1_interventions import verify_arm_interventions
from scripts.verify_safeact_v1_sources import verify_sources

UPSTREAM_REVISION = "841816cf1e376e6fbf8600cffac5df1736e1d369"
EXPECTED_CASES = 131
MODES = ("ungated", "routing_only", "evidence_gate")


def public_case_ids(root: Path) -> set[str]:
    result = subprocess.run(
        [
            sys.executable,
            str(root / "run_benchmark.py"),
            "--list-only",
            "--protocol",
            "v1",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_CASES:
        raise ValueError("official public V1 listing must contain 131 cases")
    ids = [row.get("case_id") for row in tasks if isinstance(row, dict)]
    if len(ids) != EXPECTED_CASES or any(
        not isinstance(value, str) or not value for value in ids
    ):
        raise ValueError("official V1 case identities are malformed")
    if len(set(ids)) != EXPECTED_CASES:
        raise ValueError("duplicate official V1 case IDs")
    return set(ids)


def _declared_model(command: str) -> str | None:
    tokens = shlex.split(command)
    found: list[str] = []
    for index, token in enumerate(tokens):
        if token == "--model" and index + 1 < len(tokens):
            found.append(tokens[index + 1])
        elif token.startswith("--model="):
            found.append(token.partition("=")[2])
    return found[0] if len(found) == 1 and found[0] else None


def validate_launch(
    *,
    safeact_root: Path,
    model: str,
    commands: dict[str, str],
    contracts: dict,
    public_source_root: Path,
    intervention_manifest: dict,
) -> tuple[V1RunPlan, ...]:
    """Check frozen official code, source identities and arm policy coverage."""
    root = safeact_root.resolve(strict=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    if revision != UPSTREAM_REVISION:
        raise ValueError("official SafeAct revision mismatch")
    if not model.strip():
        raise ValueError("frozen model identity must be nonempty")
    if set(commands) != set(CONDITIONS) or len(set(commands.values())) != 3:
        raise ValueError("three unique preregistered agent commands required")
    plans = validate_comparison_matrix(
        [
            V1RunPlan(name, root, model, commands[name])
            for name in CONDITIONS
        ]
    )
    if any(_declared_model(plan.agent_command) != model for plan in plans):
        raise ValueError("each arm must explicitly declare the frozen model")

    errors = verify_sources(contracts, public_source_root)
    if errors:
        raise ValueError("unverified independent sources: " + "; ".join(errors))

    coverage = contracts.get("case_coverage")
    if not isinstance(coverage, dict):
        raise ValueError("explicit independent V1 case coverage required")
    if set(coverage) != public_case_ids(root):
        raise ValueError("independent contracts do not cover 131 public V1 cases")
    names = [
        contract.get("action")
        for contract in contracts["contracts"]
        if isinstance(contract, dict)
    ]
    if (
        not names
        or any(not isinstance(name, str) or not name for name in names)
        or len(set(names)) != len(names)
    ):
        raise ValueError("independent action contracts must have unique names")
    available = set(names)
    if any(
        not isinstance(action, str) or action not in available
        for action in coverage.values()
    ):
        raise ValueError("case coverage references missing action contract")

    declared_arms = intervention_manifest.get("conditions")
    if not isinstance(declared_arms, dict):
        raise ValueError("trusted intervention declaration missing")
    for name, mode in zip(CONDITIONS, MODES, strict=True):
        entry = declared_arms.get(name)
        if (
            not isinstance(entry, dict)
            or entry.get("mode") != mode
            or not isinstance(entry.get("adapter_commit"), str)
            or re.fullmatch(r"[a-f0-9]{40}", entry["adapter_commit"]) is None
            or entry.get("agent_command_sha256")
            != hashlib.sha256(commands[name].encode("utf-8")).hexdigest()
        ):
            raise ValueError("missing or altered trusted adapter identity")
    if intervention_manifest.get("reviewed") is not True:
        raise ValueError("independent adapter review must be recorded")
    return plans


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safeact-root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--public-source-root", type=Path, required=True)
    parser.add_argument("--intervention-manifest", type=Path, required=True)
    for name in CONDITIONS:
        parser.add_argument("--" + name.lower() + "-agent-cmd", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    commands = {
        name: getattr(args, name.lower().replace("-", "_") + "_agent_cmd")
        for name in CONDITIONS
    }
    contracts = json.loads(args.contracts.read_text(encoding="utf-8"))
    intervention = json.loads(
        args.intervention_manifest.read_text(encoding="utf-8")
    )
    plans = validate_launch(
        safeact_root=args.safeact_root,
        model=args.model,
        commands=commands,
        contracts=contracts,
        public_source_root=args.public_source_root,
        intervention_manifest=intervention,
    )
    for plan in plans:
        print(plan.command_string(), flush=True)
    if not args.execute:
        print("Preflight only; no agent calls or SafeAct scores generated.")
        return 0
    for plan in plans:
        result = subprocess.run(plan.argv(), cwd=plan.safeact_root, check=False)
        if result.returncode != 0:
            raise SystemExit(
                f"Official agent run failed in {plan.condition}: "
                f"exit {result.returncode}"
            )
    verify_arm_interventions(
        {plan.condition: Path(plan.argv()[-1]) for plan in plans},
        expected_cases=EXPECTED_CASES,
    )
    report = aggregate_scored_v1(
        {plan.condition: Path(plan.argv()[-1]) for plan in plans},
        expected_cases=EXPECTED_CASES,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail-closed launch controller for a real, paired SafeAct V1 experiment.

No evaluator/gold files are read while authoring contracts or launching cases.
Pass --execute only after independent review of the official agent bridges.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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

# Pinned upstream CLI solver/runtime flags. All three arms must use the same
# effective explicit values, including repeated --extra-arg switches.
UNIFORM_RUNTIME_OPTIONS = (
    "--profile",
    "--cfuse-config",
    "--cli-bin",
    "--model-catalog",
    "--timeout",
    "--max-turns",
    "--extra-arg",
)


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


def _declared_options(command: str, option: str) -> tuple[str, ...]:
    """Extract option values while rejecting broken spaced flag forms."""
    tokens = shlex.split(command)
    found: list[str] = []
    for index, token in enumerate(tokens):
        if token == option:
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
                raise ValueError(f"{option} requires a nonempty argument")
            found.append(tokens[index + 1])
        elif token.startswith(option + "="):
            value = token.partition("=")[2]
            if not value:
                raise ValueError(f"{option} requires a nonempty argument")
            found.append(value)
    return tuple(found)


def _declared_option(command: str, option: str) -> str | None:
    """Return at most one declared value, rejecting duplicate flags."""
    found = _declared_options(command, option)
    if len(found) > 1:
        raise ValueError(f"duplicate {option} declarations")
    return found[0] if found else None


def _declared_model(command: str) -> str | None:
    return _declared_option(command, "--model")


def _validate_agent_fairness(plans: tuple[V1RunPlan, ...]) -> None:
    """Require one explicitly identical model/backend/baseline strategy.

    The official SafeAct CLI defaults its strategy from environment variables.
    A silently enabled upstream SCGR treatment would invalidate the causal
    interpretation even if the SchemaRouter interventions were correct.
    """
    backends = {_declared_option(p.agent_command, "--backend") for p in plans}
    if len(backends) != 1 or not backends <= {"codex", "claude"}:
        raise ValueError("all V1 arms must declare the same official backend")
    if any(
        _declared_option(p.agent_command, "--strategy") != "baseline"
        for p in plans
    ):
        raise ValueError("all V1 arms must explicitly declare baseline strategy")
    for option in UNIFORM_RUNTIME_OPTIONS:
        values = {
            _declared_options(plan.agent_command, option)
            for plan in plans
        }
        if len(values) != 1:
            raise ValueError(
                f"all V1 arms must use the same upstream runtime {option}"
            )
    keep_sandbox = {
        "--keep-sandbox" in shlex.split(plan.agent_command)
        for plan in plans
    }
    if len(keep_sandbox) != 1:
        raise ValueError("all V1 arms must agree on --keep-sandbox")


def validate_independent_contract_review(
    manifest: dict, *, contract_sha256: str
) -> None:
    """Require a separately recorded contract review before any scored launch.

    This validates an attestation's structure and frozen identity. It is NOT
    cryptographic proof that human review happened: reviewers must verify the
    actual public-policy authoring process independently.
    """
    review = manifest.get("independent_contract_review")
    if not isinstance(review, dict) or review.get("approved") is not True:
        raise ValueError("independent contract review approval is required")
    author = review.get("author")
    reviewer = review.get("reviewer")
    if (
        not isinstance(author, str)
        or not author.strip()
        or not isinstance(reviewer, str)
        or not reviewer.strip()
        or author.strip().casefold() == reviewer.strip().casefold()
    ):
        raise ValueError("independent contract author and reviewer must differ")
    if review.get("contract_sha256") != contract_sha256:
        raise ValueError("independent contract review digest does not match frozen contract")
    if review.get("upstream_revision") != UPSTREAM_REVISION:
        raise ValueError("independent contract review upstream revision mismatch")


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
    _validate_agent_fairness(plans)

    frozen_contract_hash = hashlib.sha256(
        json.dumps(
            contracts, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if intervention_manifest.get("contract_sha256") != frozen_contract_hash:
        raise ValueError("independent contract snapshot hash changed")
    validate_independent_contract_review(
        intervention_manifest, contract_sha256=frozen_contract_hash
    )
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
    # Public V1 IDs are an opaque cohort, never a per-case expected-action oracle.
    # Each actual model-proposed tool must select its own reviewed contract.
    if any(value is not None for value in coverage.values()):
        raise ValueError("case-specific expected-action oracle is forbidden")

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
    parser.add_argument("--report", type=Path, default=None)
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
        # Upstream otherwise allows ambient strategy overrides via the parent
        # environment, which could change the ungated arm independently.
        result = subprocess.run(
            plan.argv(),
            cwd=plan.safeact_root,
            check=False,
            env={**os.environ, "SAFEACT_AGENT_STRATEGY": "baseline"},
        )
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
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

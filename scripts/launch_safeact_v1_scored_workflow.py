"""Fail-closed official SafeAct V1 scored-run readiness and launch wrapper.

PR/default dry-runs never execute models. Never manufacture author/reviewer
approval, runtime credentials, hidden labels, or scored benchmark output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from examples.external_validation.safeact_v1.run_plan import CONDITIONS
from scripts.run_safeact_v1_scored import validate_launch


def inspect(
    *,
    safeact_root: Path,
    contracts_path: Path,
    source_root: Path,
    manifest_path: Path,
    model: str,
) -> tuple[dict, dict[str, str] | None]:
    """Return a non-scored status, including explicit missing prerequisites."""
    report: dict = {
        "kind": "safeact_v1_scored_launch_readiness",
        "official_scored_run_started": False,
        "model_calls": 0,
        "approved_contracts_assumed": False,
        "ready": False,
        "blockers": [],
    }
    blockers: list[str] = report["blockers"]
    files = {
        "pinned upstream checkout": safeact_root / ".git",
        "independently reviewed contract document": contracts_path,
        "public contract source directory": source_root,
        "reviewed intervention manifest": manifest_path,
    }
    for description, path in files.items():
        if not path.exists():
            blockers.append(f"missing {description}: {path}")
    if not model.strip():
        blockers.append("missing explicitly frozen model identity")
    if blockers:
        return report, None
    try:
        contract = json.loads(contracts_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict) or not isinstance(manifest, dict):
            raise ValueError("contracts and manifest must be JSON objects")
        declared = manifest.get("conditions")
        if not isinstance(declared, dict):
            raise ValueError("missing three trusted condition declarations")
        # The approved template SHA is frozen independently of ephemeral
        # GitHub-hosted and self-hosted checkout paths. Expansion is restricted
        # to the two verified checkout roots; no shell interpolation/eval.
        commands: dict[str, str] = {}
        effective_manifest = json.loads(json.dumps(manifest))
        replacements = {
            "@SAFEACT_ROOT@": str(safeact_root.resolve(strict=True)),
            "@SCHEMAROUTER_ROOT@": str(Path(__file__).resolve().parents[1]),
        }
        for condition in CONDITIONS:
            row = declared.get(condition)
            template = row.get("agent_command") if isinstance(row, dict) else None
            if not isinstance(template, str) or not template.strip():
                raise ValueError(f"{condition}: missing reviewed agent_command")
            digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
            if row.get("agent_command_sha256") != digest:
                raise ValueError(
                    f"{condition}: reviewed command template digest mismatch"
                )
            expanded = template
            for token, root_path in replacements.items():
                expanded = expanded.replace(token, root_path)
            if "@" in expanded:
                raise ValueError(f"{condition}: unrecognized command placeholder")
            commands[condition] = expanded
            effective_manifest["conditions"][condition][
                "reviewed_command_template_sha256"
            ] = digest
            effective_manifest["conditions"][condition][
                "agent_command_sha256"
            ] = hashlib.sha256(expanded.encode("utf-8")).hexdigest()
        # A reviewed command digest alone does not establish that the expected
        # official host adapter is actually invoked. Never permit arbitrary
        # agent executable substitution on a credentialed self-hosted runner.
        expected_scripts = {
            CONDITIONS[0]: safeact_root / "agents" / "coding_cli_safeact_agent.py",
            CONDITIONS[1]: (
                Path(__file__).resolve().parents[1]
                / "examples/external_validation/safeact_v1/official_routing_hook.py"
            ),
            CONDITIONS[2]: (
                Path(__file__).resolve().parents[1]
                / "examples/external_validation/safeact_v1/official_agent_hook.py"
            ),
        }
        permitted_python = {
            "python", "python3", "python3.11", "python3.12", "python3.13", "python3.14",
        }
        for condition, command in commands.items():
            tokens = shlex.split(command)
            if (
                len(tokens) < 3
                or Path(tokens[0]).name not in permitted_python
                or Path(tokens[1]).resolve(strict=True)
                != expected_scripts[condition].resolve(strict=True)
            ):
                raise ValueError(
                    f"{condition}: untrusted official host adapter command"
                )
        # Performs the pinned upstream checkout identity, full 131 public IDs,
        # canonical contract digest, independent source and human review
        # attestations, cross-arm runner equality and adapter command hashes.
        validate_launch(
            safeact_root=safeact_root,
            model=model,
            commands=commands,
            contracts=contract,
            public_source_root=source_root,
            intervention_manifest=effective_manifest,
        )
        report["ready"] = True
        report["approved_contracts_assumed"] = False  # structure != true review
        report["review_attestation_structurally_valid"] = True
        report["case_count"] = 131
        report["arm_count"] = len(CONDITIONS)
        return report, commands
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        blockers.append(f"scored launch validation refused: {type(exc).__name__}: {exc}")
        return report, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safeact-root", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--public-source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scored-report", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    status, commands = inspect(
        safeact_root=args.safeact_root,
        contracts_path=args.contracts,
        source_root=args.public_source_root,
        manifest_path=args.manifest,
        model=args.model,
    )
    if args.execute:
        if os.environ.get("SAFEACT_V1_RUNTIME_VERIFIED") != "1":
            status["blockers"].append(
                "missing trusted model-runtime authorization on protected runner"
            )
            status["ready"] = False
        if os.environ.get("GITHUB_REF") != "refs/heads/main":
            status["blockers"].append(
                "scored execution requires protected default main branch"
            )
            status["ready"] = False
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, sort_keys=True), flush=True)

    if not args.execute:
        # Pull requests publish a non-scored readiness report even when blocked.
        # Explicit dispatch instead fails closed before reserving a model runner.
        return 2 if args.require_ready and not status["ready"] else 0
    if not status["ready"] or commands is None:
        return 2
    # The reviewed template hash was checked above. Bind the expanded commands
    # to immutable, verified checkout paths for the child controller without
    # altering the separately reviewed source manifest.
    approved_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for condition in CONDITIONS:
        row = approved_manifest["conditions"][condition]
        row["reviewed_command_template_sha256"] = row["agent_command_sha256"]
        row["agent_command_sha256"] = hashlib.sha256(
            commands[condition].encode("utf-8")
        ).hexdigest()
    runtime_manifest = args.report.parent / "safeact-v1-expanded-runtime-manifest.json"
    runtime_manifest.write_text(
        json.dumps(approved_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8",
    )
    # The real scored controller revalidates all above conditions before any
    # model call and checks 131 paired outcomes per arm after completion.
    argv = [
        sys.executable, "-m", "scripts.run_safeact_v1_scored",
        "--safeact-root", str(args.safeact_root),
        "--model", args.model,
        "--contracts", str(args.contracts),
        "--public-source-root", str(args.public_source_root),
        "--intervention-manifest", str(runtime_manifest),
    ]
    for condition in CONDITIONS:
        argv.extend([
            "--" + condition.lower() + "-agent-cmd", commands[condition]
        ])
    if args.scored_report is not None:
        argv.extend(["--report", str(args.scored_report)])
    argv.append("--execute")
    print("Starting official 131 x 3 V1 model trajectories", flush=True)
    result = subprocess.run(argv, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded, local AutoResearch one-trial KEEP/DISCARD/CRASH controller.

An external coding agent may *edit only* research/autoresearch/candidate.py
before invoking this script in an isolated working tree. No LLM or network
API is invoked here. Failed/rejected trials restore only that candidate from
HEAD, never change product files, create GitHub PRs or promote releases.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.research_autoresearch_sandbox import PROTECTED, ROOT, SCIENTIFIC_SCOPE, sha

EDITABLE = "research/autoresearch/candidate.py"
FIXED_TEST = "tests/test_research_autoresearch_sandbox.py"
EVALUATOR = "scripts.research_autoresearch_sandbox"
HISTORY = "experiment-history.jsonl"


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    )


def checked_out_candidate_at_head() -> bytes:
    return _git(["show", f"HEAD:{EDITABLE}"]).stdout.encode("utf-8")


def protected_worktree_clean() -> bool:
    changed = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *PROTECTED],
        cwd=ROOT, capture_output=True, timeout=10, check=False,
    )
    if changed.returncode not in (0, 1):
        raise RuntimeError("cannot verify protected source from git")
    return changed.returncode == 0


def safe_environment() -> dict[str, str]:
    """Pass only unprivileged runtime variables, never tokens or credentials."""
    safe = ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "PYTHONIOENCODING")
    return {key: value for key in safe if (value := os.environ.get(key)) is not None}


def run_registered(args: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    if timeout < 1 or timeout > 180:
        raise ValueError("trial process budget exceeded")
    allowed = (
        ["-m", "pytest", "-q", FIXED_TEST],
        ["-m", EVALUATOR, "--sizes", "100", "250", "500",
         "--cases-per-group", "1"],
    )
    if args != allowed[0] and args[:len(allowed[1])] != allowed[1]:
        raise ValueError("unregistered program invocation")
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT, capture_output=True, text=True,
        check=False, timeout=timeout, env=safe_environment(),
    )


def verdict(report: dict[str, Any], *, candidate_hash: str) -> str:
    if (
        not isinstance(report, dict)
        or report.get("id") != "schemarouter-autoresearch-ranking-sandbox-v1"
        or report.get("research_scope") != SCIENTIFIC_SCOPE
        or not isinstance(report.get("source_sha256"), dict)
        or report["source_sha256"].get(EDITABLE) != candidate_hash
        or report.get("evaluated_requests") != 144
        or report.get("sizes") != [100, 250, 500]
        or report.get("scored_k") != [3, 5, 10]
        or report.get("candidate_pool_k") != 24
        or not isinstance(report.get("decision"), dict)
        or report["decision"].get("can_merge_product_code") is not False
        or report["decision"].get("independent_qualification") is not False
    ):
        raise ValueError("unregistered, partial or falsely qualified trial report")
    status = report["decision"].get("decision")
    if status not in ("KEEP_RESEARCH_CANDIDATE", "DISCARD_OR_REVISE"):
        raise ValueError("invalid candidate trial decision")
    return "keep" if status == "KEEP_RESEARCH_CANDIDATE" else "discard"


def append_history(folder: Path, event: dict[str, Any]) -> None:
    target = folder / HISTORY
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=True,
                                allow_nan=False) + "\n")


def execute_one_trial(folder: Path, *, description: str) -> dict[str, Any]:
    if not description or len(description) > 180 or "\n" in description:
        raise ValueError("trial description must be nonempty and one short line")
    if not protected_worktree_clean():
        raise RuntimeError("protected scorer or source differs from HEAD")
    folder.mkdir(parents=True, exist_ok=True)
    candidate_file = ROOT / EDITABLE
    head_contents = checked_out_candidate_at_head()
    candidate_hash = sha(candidate_file)
    commit = _git(["rev-parse", "HEAD"]).stdout.strip()
    results_path = folder / "current-trial-report.json"
    event: dict[str, Any] = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "candidate_sha256": candidate_hash,
        "research_only": True,
        "description": description,
        "status": "crash",
        "score": None,
        "error": None,
        "restored_head_candidate": False,
        "may_promote_product": False,
        "may_release": False,
    }
    original_protected_hashes = {path: sha(ROOT / path) for path in PROTECTED}
    try:
        tests = run_registered(["-m", "pytest", "-q", FIXED_TEST])
        (folder / "test.log").write_text(
            tests.stdout[-12000:] + "\n" + tests.stderr[-3000:],
            encoding="utf-8",
        )
        if tests.returncode:
            raise RuntimeError(f"research guards failed (exit {tests.returncode})")
        result = run_registered([
            "-m", EVALUATOR, "--sizes", "100", "250", "500",
            "--cases-per-group", "1", "--output", str(results_path),
        ])
        (folder / "eval.log").write_text(
            result.stdout[-12000:] + "\n" + result.stderr[-3000:],
            encoding="utf-8",
        )
        if result.returncode or not results_path.is_file():
            raise RuntimeError(f"registered candidate evaluation failed ({result.returncode})")
        report = json.loads(results_path.read_text(encoding="utf-8"))
        event["status"] = verdict(report, candidate_hash=candidate_hash)
        event["score"] = report["decision"]["top5_required_route_gain"]
        if {path: sha(ROOT / path) for path in PROTECTED} != original_protected_hashes:
            raise RuntimeError("candidate mutated protected source")
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        event["status"] = "crash"
        event["score"] = None
        event["error"] = str(exc)[:300]
    finally:
        if event["status"] != "keep":
            # Scoped rollback: NEVER 'git reset --hard' or mutate other work.
            candidate_file.write_bytes(head_contents)
            event["restored_head_candidate"] = True
        append_history(folder, event)
        (folder / "last-trial.json").write_text(
            json.dumps(event, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return event


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path,
                    default=Path("artifacts/autoresearch-trials"))
    ap.add_argument("--description", required=True)
    args = ap.parse_args()
    event = execute_one_trial(args.output_dir.resolve(), description=args.description)
    print(json.dumps({
        "status": event["status"],
        "top5_required_route_gain": event["score"],
        "restored_head_candidate": event["restored_head_candidate"],
        "research_only": True,
    }))
    return 1 if event["status"] == "crash" else 0


if __name__ == "__main__":
    raise SystemExit(main())

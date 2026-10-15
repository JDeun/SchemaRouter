"""Fail-closed dispatch decision for consecutive GitHub Actions CPU experiments.

No code generation, scheduling, secrets, deployment, or GitHub API here.
The only output is a yes/no permission for a separately privileged dispatch job.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MAX_BATCHES = 12
_SHA = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^[a-f0-9]{40}$")


def should_dispatch(report: Any, state: Any, remaining: int) -> bool:
    if type(remaining) is not int or not 1 <= remaining <= MAX_BATCHES:
        raise ValueError("out-of-range Actions run chain budget")
    if not isinstance(report, dict) or not isinstance(state, dict):
        raise ValueError("missing bounded experiment receipt")
    if (
        report.get("schema_version") != 1
        or state.get("schema_version") != 1
        or report.get("status") != "ACTIONS_CPU_RESEARCH_ONLY"
        or report.get("may_promote_to_product") is not False
        or report.get("independent_validation") is not False
        or report.get("search_space") != "continuous_safe_weights_not_generated_code"
        or not isinstance(report.get("source_commit"), str)
        or _COMMIT.fullmatch(report["source_commit"]) is None
        or not isinstance(report.get("contract_sha256"), str)
        or _SHA.fullmatch(report["contract_sha256"]) is None
        or report["contract_sha256"] != state.get("contract_sha256")
    ):
        raise ValueError("unverified or privileged research result")
    history = report.get("history")
    epoch, prior = state.get("epoch"), report.get("previous_epoch")
    generated = report.get("total_new_trials")
    if (
        not isinstance(history, list)
        or type(generated) is not int or not 0 <= generated <= 64
        or generated != len(history)
        or type(epoch) is not int or not 1 <= epoch <= MAX_BATCHES
        or type(prior) is not int or epoch != prior + 1
        or report.get("new_epoch") != epoch
        or type(state.get("total_trials")) is not int
        or state["total_trials"] < generated
        or (epoch + remaining - 1) > MAX_BATCHES
    ):
        raise ValueError("experiment state/budget divergence")
    if report.get("champion") != state.get("champion"):
        raise ValueError("champion differs from preserved state")
    # Never turn a synthetic DEV-only champion into a production stop/success.
    # Continue for remaining budget unless no unique configuration was scored.
    return remaining > 1 and generated > 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--remaining", required=True, type=int)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    keep_running = should_dispatch(report, state, args.remaining)
    print(f"continue_next={'true' if keep_running else 'false'}")
    print(f"remaining_next={args.remaining - 1 if keep_running else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

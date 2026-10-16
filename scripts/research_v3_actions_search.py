"""Finite GitHub Actions-only V3 width+weight adaptive search.

Self-search changes only an approved numeric genome, never executable code,
policy, tool registry or benchmark gold. Each run uses genuine current
SchemaPlanner CPU retrieval at six widths. All data is *exposed synthetic DEV*.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import build_tasks
from research.autoresearch.actions_ranker import generate, validate
from scripts.research_actions_width_search_dev import split_fixture
from scripts.research_autoresearch_sandbox import decide
from scripts.research_current_main_multilingual_dev import encoded
from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes
from scripts.research_v3_width_pareto_cpu_dev import (
    MAX_TOTAL_P95_MS,
    MAX_V1_P95_MULTIPLIER,
    WIDTHS,
    evaluate_width,
    preload,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_BATCHES = 6
MAX_TRIALS_PER_BATCH = 12
SOURCE_FILES = (
    "scripts/research_v3_actions_search.py",
    "scripts/research_v3_width_pareto_cpu_dev.py",
    "scripts/research_v1_v2_paired_cpu_dev.py",
    "scripts/research_autoresearch_sandbox.py",
    "scripts/research_actions_width_search_dev.py",
    "research/autoresearch/actions_ranker.py",
    ".github/workflows/research-actions-v3-continue.yml",
    "benchmarks/autoresearch-v1-v2-frozen-incumbents.json",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
)


def valid_genome(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"width", "weights"}:
        raise ValueError("unregistered or code-carrying optimizer genome")
    if type(value["width"]) is not int or value["width"] not in WIDTHS:
        raise ValueError("unreviewed CPU retrieval width")
    return {"width": value["width"], "weights": validate(value["weights"])}


def identity() -> str:
    digests = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_FILES
    }
    return hashlib.sha256(encoded({
        "schema_version": 1,
        "sources": digests,
        "v5_corpus_sha256": hashlib.sha256(encoded(build_tasks())).hexdigest(),
        "pool_widths": list(WIDTHS),
        "strict_cpu_multiplier": MAX_V1_P95_MULTIPLIER,
        "max_batches": MAX_BATCHES,
        "max_trials_per_batch": MAX_TRIALS_PER_BATCH,
    })).hexdigest()


def state_from_artifact(path: Path | None, contract: str) -> dict[str, Any]:
    state = {
        "schema_version": 1, "contract_sha256": contract, "epoch": 0,
        "total_trials": 0, "seen": [], "champion": None,
        "best_internal_score": None,
    }
    if path is None:
        return state
    saved = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(saved, dict)
        or set(saved) != set(state)
        or saved["schema_version"] != 1
        or saved["contract_sha256"] != contract
        or type(saved["epoch"]) is not int
        or not 0 <= saved["epoch"] < MAX_BATCHES
        or type(saved["total_trials"]) is not int
        or saved["total_trials"] < 0
        or not isinstance(saved["seen"], list)
        or len(saved["seen"]) > MAX_BATCHES * MAX_TRIALS_PER_BATCH
        or any(
            type(entry) is not str or len(entry) != 64
            for entry in saved["seen"]
        )
    ):
        raise ValueError("untrusted or incompatible previous Actions experiment state")
    # An artifact's config hashes are the deduplicated attempted-trial ledger.
    # A forged count, repeated entry, or impossible epoch must fail closed.
    if (
        len(saved["seen"]) != saved["total_trials"]
        or len(set(saved["seen"])) != len(saved["seen"])
        or saved["total_trials"] > saved["epoch"] * MAX_TRIALS_PER_BATCH
        or any(any(c not in "0123456789abcdef" for c in entry)
               for entry in saved["seen"])
    ):
        raise ValueError("inconsistent previous Actions trial ledger")
    if saved["champion"] is not None:
        saved["champion"] = valid_genome(saved["champion"])
        if hashlib.sha256(encoded(saved["champion"])).hexdigest() not in saved["seen"]:
            raise ValueError("research champion missing from attempted-trial ledger")
    score = saved["best_internal_score"]
    if score is not None and (
        type(score) not in (int, float) or not math.isfinite(score)
    ):
        raise ValueError("invalid state score")
    if (score is None) != (saved["champion"] is None):
        raise ValueError("unpaired champion and internal DEV score")
    return saved


def propose(
    rng: random.Random,
    parent: dict[str, Any] | None,
    old_v2: dict[str, Any],
) -> dict[str, Any]:
    if parent is None or rng.random() < 0.25:
        return valid_genome({
            "width": rng.choice(WIDTHS),
            "weights": generate(rng, None, None),
        })
    width = parent["width"] if rng.random() < 0.55 else rng.choice(WIDTHS)
    return valid_genome({
        "width": width,
        "weights": generate(rng, parent["weights"], old_v2["weights"]),
    })


def run(
    *, previous: dict[str, Any], trials: int = 12,
    cases_per_group: int = 5, seed: int = 1412,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(trials) is not int or not 1 <= trials <= MAX_TRIALS_PER_BATCH:
        raise ValueError("unbounded CPU experiment count requested")
    if type(seed) is not int or seed < 0:
        raise ValueError("invalid reproducible research seed")
    current_contract = identity()
    if previous["contract_sha256"] != current_contract:
        raise ValueError("source/corpus/research protocol drift")
    if not 0 <= previous["epoch"] < MAX_BATCHES:
        raise ValueError("expired finite Actions chain")
    v1, v2, frozen = frozen_genomes()
    fit, check = split_fixture(cases_per_group)
    fit_ids = {x["task_id"] for x in fit}
    check_ids = {x["task_id"] for x in check}
    if fit_ids & check_ids:
        raise ValueError("train/test overlap inside exposed DEV")
    all_inputs = preload(cases_per_group=cases_per_group)
    fit_inputs = [
        x for x in all_inputs if x["case"]["task_id"] in fit_ids
    ]
    check_inputs = [
        x for x in all_inputs if x["case"]["task_id"] in check_ids
    ]
    expected = len(fit_ids) * 3, len(check_ids) * 3
    if (len(fit_inputs), len(check_inputs)) != expected:
        raise ValueError("missing balanced current registered tasks")
    v1_fit, _, v1_fit_p95 = evaluate_width(
        fit_inputs, width=v1["width"], weights=v1["weights"],
    )
    v1_check, _, v1_check_p95 = evaluate_width(
        check_inputs, width=v1["width"], weights=v1["weights"],
    )
    rng = random.Random(seed + previous["epoch"] * 1009)
    seen = set(previous["seen"])
    champion = previous["champion"]
    highest = previous["best_internal_score"]
    records: list[dict[str, Any]] = []
    for index in range(trials):
        if previous["epoch"] == 0 and index == 0:
            genome = valid_genome({
                "width": 56, "weights": v2["weights"],
            })
        elif previous["epoch"] == 0 and index == 1:
            genome = valid_genome({
                "width": 40, "weights": v2["weights"],
            })
        else:
            genome = propose(rng, champion, v2)
        fid = hashlib.sha256(encoded(genome)).hexdigest()
        if fid in seen:
            continue
        seen.add(fid)
        train, train_rank_p95, train_full_p95 = evaluate_width(
            fit_inputs, width=genome["width"], weights=genome["weights"],
        )
        fit_decision = decide(v1_fit, train, candidate_p95_ms=train_rank_p95)
        fit_good = (
            fit_decision["decision"] == "KEEP_RESEARCH_CANDIDATE"
            and train_full_p95 <= MAX_TOTAL_P95_MS
            and train_full_p95 <= MAX_V1_P95_MULTIPLIER * v1_fit_p95
        )
        record: dict[str, Any] = {
            "config_sha256": fid, "genome": genome,
            "fit_top5_required_route_gain": fit_decision["top5_required_route_gain"],
            "fit_no_group_regression": not fit_decision["regressions"],
            "fit_rank_p95_ms": round(train_rank_p95, 5),
            "fit_total_p95_ms": round(train_full_p95, 5),
            "fit_pass": fit_good,
            "internal_dev_checked": False, "internal_dev_pass": False,
        }
        if fit_good:
            tested, check_rank_p95, check_full_p95 = evaluate_width(
                check_inputs, width=genome["width"], weights=genome["weights"],
            )
            gate = decide(v1_check, tested, candidate_p95_ms=check_rank_p95)
            good = (
                gate["decision"] == "KEEP_RESEARCH_CANDIDATE"
                and check_full_p95 <= MAX_TOTAL_P95_MS
                and check_full_p95 <= MAX_V1_P95_MULTIPLIER * v1_check_p95
            )
            record["internal_dev_checked"] = True
            record["internal_dev_pass"] = good
            record["internal_dev_top5_gain"] = gate["top5_required_route_gain"]
            record["internal_dev_total_p95_ms"] = round(check_full_p95, 5)
            if good:
                score = sum(
                    x["found_required_count"] for x in tested if x["k"] == 5
                )
                if highest is None or score > highest:
                    highest, champion = score, genome
        records.append(record)
    state = {
        "schema_version": 1, "contract_sha256": current_contract,
        "epoch": previous["epoch"] + 1,
        "total_trials": previous["total_trials"] + len(records),
        "seen": sorted(seen),
        "champion": champion, "best_internal_score": highest,
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    report = {
        "schema_version": 1,
        "status": "V3_FINITE_ACTIONS_RESEARCH_ONLY",
        "source_commit": commit,
        "contract_sha256": current_contract,
        "previous_epoch": previous["epoch"], "new_epoch": state["epoch"],
        "new_trials": len(records), "history": records,
        "champion": champion,
        "v1_artifact_sha256": frozen["v1"]["content_sha256"],
        "v2_artifact_sha256": frozen["v2"]["content_sha256"],
        "candidate_pools": list(WIDTHS),
        "fit_requests": len(fit_inputs), "internal_check_requests": len(check_inputs),
        "actual_planner_calls": len(all_inputs) * len(WIDTHS),
        "scope": {
            "exposed_synthetic_dev_only": True,
            "both_incumbents_tuned_on_same_generator": True,
            "independent_confirmation": False,
            "field_or_agent_utility": False,
            "automatic_product_promotion": False,
            "may_release": False,
        },
        "hardware": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "github_actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }
    return report, state


def validate_resume_budget(previous: dict[str, Any], remaining: int) -> None:
    """Reject mismatched workflow inputs before allocating the research CPU budget."""
    if (
        type(remaining) is not int
        or not 1 <= remaining <= MAX_BATCHES
        or type(previous.get("epoch")) is not int
        or previous["epoch"] + remaining != MAX_BATCHES
    ):
        raise ValueError("remaining Actions budget does not match predecessor epoch")


def continue_chain(report: dict[str, Any], state: dict[str, Any], remaining: int) -> bool:
    if type(remaining) is not int or not 1 <= remaining <= MAX_BATCHES:
        raise ValueError("unregistered continuation budget")
    if (
        report.get("schema_version") != 1
        or report.get("status") != "V3_FINITE_ACTIONS_RESEARCH_ONLY"
        or state.get("schema_version") != 1
        or report.get("contract_sha256") != state.get("contract_sha256")
        or state.get("epoch") != report.get("new_epoch")
        or type(state.get("epoch")) is not int
        or report.get("previous_epoch") != state["epoch"] - 1
        or state["epoch"] + remaining - 1 != MAX_BATCHES
        or report.get("champion") != state.get("champion")
        or report.get("scope", {}).get("may_release") is not False
        or report.get("scope", {}).get("automatic_product_promotion") is not False
        or not isinstance(report.get("history"), list)
        or report.get("new_trials") != len(report["history"])
    ):
        raise ValueError("tampered report or exhausted Actions chain")
    return remaining > 1 and report["new_trials"] > 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--cases-per-group", type=int, choices=(2, 5), default=5)
    parser.add_argument("--seed", type=int, default=1412)
    parser.add_argument("--previous-state", type=Path)
    parser.add_argument("--remaining", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    state = state_from_artifact(args.previous_state, identity())
    validate_resume_budget(state, args.remaining)
    report, next_state = run(
        previous=state, trials=args.trials,
        cases_per_group=args.cases_per_group, seed=args.seed,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("report.json", report), ("state.json", next_state)):
        (args.output_dir / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    continuing = continue_chain(report, next_state, args.remaining)
    print(json.dumps({
        "status": report["status"], "epoch": next_state["epoch"],
        "trials": report["new_trials"],
        "champion_exists": next_state["champion"] is not None,
        "continue_next": continuing, "independent": False,
    }))
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(
                f"continue_next={'true' if continuing else 'false'}\n"
                f"remaining_next={args.remaining - 1 if continuing else 0}\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

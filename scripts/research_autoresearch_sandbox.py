"""Frozen-side AutoResearch evaluator for *current* typed retrieval, DEV only.

Scores the existing current-main SchemaPlanner ranking and one mutable
research-only candidate on identical registered K=24 pools. The candidate is
untrusted code in a separate local JSONL process. This process NEVER calls
SchemaRouter.execute or sends credentials to the candidate. It is a DEV
experiment harness, not an agent or independent production qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import select
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    TASKS_PER_CELL,
    build_registry,
    build_tasks,
)
from schemarouter import PlanRequest, SchemaPlanner
from scripts.research_current_main_multilingual_dev import (
    KS,
    encoded,
    score_case,
    select_cases,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "research/autoresearch/worker.py"
CANDIDATE = ROOT / "research/autoresearch/candidate.py"
POOL_K = 24
MAX_CPU_DEV_CASES_PER_GROUP = TASKS_PER_CELL
SCIENTIFIC_SCOPE = {
    "corpus": "historical_preexposed_synthetic_dev_not_independent",
    "editable_area": "research/autoresearch/candidate.py",
    "actual_agent_task_success": False,
    "live_heterogeneous_providers": False,
    "required_output_field_gold": False,
    "authorization_or_execution_tested": False,
    "model_or_llm_training_executed": False,
    "autonomous_code_generation": False,
    "independent_confirmation": False,
    "may_promote": False,
    "may_release": False,
}
PROTECTED = (
    "scripts/research_autoresearch_sandbox.py",
    "research/autoresearch/worker.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "scripts/research_current_main_multilingual_dev.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/models.py",
    "src/schemarouter/authorization.py",
    "src/schemarouter/executor.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {path: sha(ROOT / path) for path in (*PROTECTED, "research/autoresearch/candidate.py")}


def verify_permutation(input_ids: list[str], output: Any) -> list[str]:
    if (
        not isinstance(output, list)
        or len(output) != len(input_ids)
        or any(type(x) is not str for x in output)
        or len(output) != len(set(output))
        or set(output) != set(input_ids)
    ):
        raise ValueError("candidate attempted to omit, duplicate, or introduce registered routes")
    return output


def candidate_view(candidates: list[Any]) -> list[dict[str, Any]]:
    """Expose only registered public retrieval metadata, never gold labels."""
    return [
        {
            "route_id": c.route_id,
            "tool": c.tool,
            "endpoint": c.endpoint,
            "score": c.score,
            "tool_description": c.tool_description,
            "endpoint_description": c.endpoint_description,
            "matched_fields": list(c.matched_fields),
            "output_fields": [
                {"name": field.name, "semantic_id": field.semantic_id,
                 "description": field.description, "unit": field.unit}
                for field in c.output_fields
            ],
            "read_only": c.read_only,
            "destructive": c.destructive,
        }
        for c in candidates
    ]


class CandidateWorker:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None

    def __enter__(self) -> CandidateWorker:
        # No GITHUB_TOKEN, runner secrets or host application credential env
        # crosses to the worker. An untrusted Python file still needs an
        # ephemeral, low-privilege OS/container sandbox and no holdout data.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
        }
        self.process = subprocess.Popen(
            [sys.executable, "-I", str(WORKER)],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env,
        )
        return self

    def rank(self, query: str, candidates: list[dict[str, Any]]) -> tuple[list[str], float]:
        proc = self.process
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RuntimeError("candidate worker not started")
        started = time.perf_counter_ns()
        try:
            proc.stdin.write(json.dumps({
                "query": query, "candidates": candidates,
            }, ensure_ascii=True, allow_nan=False) + "\n")
            proc.stdin.flush()
            ready, _, _ = select.select([proc.stdout], [], [], 8)
            if not ready:
                raise TimeoutError("candidate IPC exceeded per-request research budget")
            raw = proc.stdout.readline()
            if not raw:
                raise RuntimeError("candidate process crashed or closed stdout")
            output = json.loads(raw)
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError("candidate worker communication failed") from exc
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        return verify_permutation([c["route_id"] for c in candidates], output), elapsed

    def __exit__(self, *_: Any) -> None:
        proc = self.process
        self.process = None
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            for stream in (proc.stdin, proc.stdout):
                if stream is not None:
                    stream.close()


def _metrics(rows: list[dict[str, Any]], size: int, k: int) -> dict[str, Any]:
    selected = [r for r in rows if r["catalog_size"] == size and r["k"] == k]
    return {
        "catalog_size": size, "k": k,
        "all": summarize(selected),
        "languages": {lang: summarize([
            r for r in selected if r["language"] == lang
        ]) for lang in LANGUAGES},
    }


def _found_per_group(
    rows: list[dict[str, Any]],
) -> dict[tuple[int, int, str], tuple[int, int]]:
    groups: dict[tuple[int, int, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (row["catalog_size"], row["k"], row["language"])
        groups[key][0] += row["found_required_count"]
        groups[key][1] += row["full_coverage"]
    return {key: tuple(value) for key, value in groups.items()}


def decide(
    baseline: list[dict[str, Any]],
    proposed: list[dict[str, Any]],
    *,
    candidate_p95_ms: float,
) -> dict[str, Any]:
    """Hard non-regression first, improvement second. No weighted safety score."""
    if (
        not math.isfinite(candidate_p95_ms)
        or candidate_p95_ms < 0
        or len(baseline) != len(proposed)
        or not baseline
    ):
        raise ValueError("invalid paired research results")
    keys = ("catalog_size", "task_id", "language", "k", "required_route_count")
    if any(tuple(a[key] for key in keys) != tuple(b[key] for key in keys)
           for a, b in zip(baseline, proposed, strict=True)):
        raise ValueError("unpaired or tampered evaluation rows")
    a, b = _found_per_group(baseline), _found_per_group(proposed)
    if set(a) != set(b):
        raise ValueError("different cohort coverage")
    regressions = [
        {"catalog_size": key[0], "k": key[1], "language": key[2],
         "before_found_and_covered": a[key],
         "after_found_and_covered": b[key]}
        for key in sorted(a) if b[key][0] < a[key][0] or b[key][1] < a[key][1]
    ]
    gain_at_5 = sum(
        row["found_required_count"] for row in proposed if row["k"] == 5
    ) - sum(row["found_required_count"] for row in baseline if row["k"] == 5)
    bytes_before = sum(r["candidate_json_bytes"] for r in baseline)
    bytes_after = sum(r["candidate_json_bytes"] for r in proposed)
    guards = {
        "paired_case_identity": True,
        "no_language_or_size_route_or_full_coverage_regression": not regressions,
        "candidate_ipc_p95_below_20_ms": candidate_p95_ms <= 20,
        "candidate_payload_bytes_within_110_percent_baseline":
            bytes_after <= bytes_before * 1.10,
    }
    return {
        "decision": (
            "KEEP_RESEARCH_CANDIDATE"
            if all(guards.values()) and gain_at_5 > 0
            else "DISCARD_OR_REVISE"
        ),
        "top5_required_route_gain": gain_at_5,
        "guard_results": guards,
        "regressions": regressions,
        "total_candidate_bytes_ratio":
            round(bytes_after / bytes_before, 5) if bytes_before else None,
        # KEEP only updates a research champion, never product/release.
        "can_merge_product_code": False,
        "independent_qualification": False,
    }


def evaluate(
    *,
    sizes: tuple[int, ...] = CATALOG_SIZES,
    cases_per_group: int = 1,
) -> dict[str, Any]:
    if (
        not sizes or tuple(sorted(sizes)) != sizes
        or len(sizes) != len(set(sizes))
        or any(s not in CATALOG_SIZES for s in sizes)
        or type(cases_per_group) is not int
        or not 1 <= cases_per_group <= MAX_CPU_DEV_CASES_PER_GROUP
    ):
        raise ValueError("invalid preregistered research evaluation budget")
    source_before = source_hashes()
    tasks = select_cases(build_tasks(), cases_per_group=cases_per_group)
    baseline_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    candidate_times: list[float] = []
    with CandidateWorker() as worker:
        for size in sizes:
            registry = build_registry(size)
            route_ids = {
                f"{tool.key}.{endpoint.name}"
                for tool in registry.tools() for endpoint in tool.endpoints
            }
            if len(route_ids) != size:
                raise ValueError("current registered typed route count drift")
            planner = SchemaPlanner(registry)
            planner._index()
            for case in tasks:
                started = time.perf_counter_ns()
                retrieval = planner.retrieve(PlanRequest(query=case["query"]), k=POOL_K)
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                original = retrieval.candidates
                views = candidate_view(original)
                ordered, ranking_ms = worker.rank(case["query"], views)
                candidate_times.append(ranking_ms)
                by_id = {item.route_id: item for item in original}
                changed = [by_id[route_id] for route_id in ordered]
                for k in KS:
                    base = score_case(
                        case, candidates=original, k=k,
                        latency_ms=elapsed, all_routes=route_ids,
                    )
                    other = score_case(
                        case, candidates=changed, k=k,
                        latency_ms=elapsed + ranking_ms, all_routes=route_ids,
                    )
                    base["catalog_size"] = size
                    other["catalog_size"] = size
                    baseline_rows.append(base)
                    candidate_rows.append(other)
    if source_hashes() != source_before:
        raise ValueError("protected or candidate source changed during measurement")
    times = sorted(candidate_times)
    if not times:
        raise ValueError("empty candidate experiment")
    p95 = times[math.ceil(0.95 * len(times)) - 1]
    decision = decide(baseline_rows, candidate_rows, candidate_p95_ms=p95)
    sha_manifest = hashlib.sha256(encoded(source_before)).hexdigest()
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "schemarouter-autoresearch-ranking-sandbox-v1",
        "research_scope": SCIENTIFIC_SCOPE.copy(),
        "source_commit": git_sha,
        "source_sha256": source_before,
        "source_manifest_sha256": sha_manifest,
        "dataset_sha256": hashlib.sha256(encoded(build_tasks())).hexdigest(),
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "actions_run": os.environ.get("GITHUB_RUN_ID"),
        },
        "candidate_pool_k": POOL_K,
        "scored_k": list(KS),
        "sizes": list(sizes),
        "cases_per_language_stratum": cases_per_group,
        "evaluated_requests": len(candidate_times),
        "candidate_worker_request_p95_ms": round(p95, 3),
        "baseline": [_metrics(baseline_rows, size, k) for size in sizes for k in KS],
        "candidate": [_metrics(candidate_rows, size, k) for size in sizes for k in KS],
        "decision": decision,
        "case_pairs": [
            {"baseline": old, "candidate": new}
            for old, new in zip(baseline_rows, candidate_rows, strict=True)
        ],
        "claim_boundary": (
            "Re-ranking only within the original registered top24 candidate pool. "
            "No new candidate generation, execution rights, field-gold, current real "
            "provider authorization, agent success, independent test, or autonomous "
            "LLM-authored source modification. KEEP means research-only promotion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=list(CATALOG_SIZES),
                        choices=CATALOG_SIZES)
    parser.add_argument("--cases-per-group", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(
        sizes=tuple(args.sizes), cases_per_group=args.cases_per_group,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "EXECUTED_RESEARCH_DEV_ONLY",
        "cases": report["evaluated_requests"],
        "decision": report["decision"]["decision"],
        "top5_required_route_gain": report["decision"]["top5_required_route_gain"],
        "candidate_worker_p95_ms": report["candidate_worker_request_p95_ms"],
        "independent": False, "product_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

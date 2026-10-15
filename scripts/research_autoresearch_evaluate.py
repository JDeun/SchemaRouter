"""Locked, observational EN/KO/JA operation-intent DEV evaluator for #1412.

The mutable candidate receives query text only and returns an untrusted operation
hypothesis or None. This does not run tools, grant permissions, certify independent
quality, or score agent task success. Run candidate code only on an unprivileged
research runner: Python import executes candidate-authored code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import runpy
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
for source_path in (ROOT, ROOT / "src"):
    if str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

from scripts.research_operation_fit_conveyor import (  # noqa: E402
    CORPUS_SHA,
    KINDS,
    load_inputs,
)

CANDIDATE = ROOT / "research/autoresearch/candidate.py"
REPORT_CLASS = "visible_development_only"
PREDICTOR = Callable[[str], str | None]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(samples: list[float], pct: float) -> float:
    if not samples or any(not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError("invalid timing samples")
    ordered = sorted(samples)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [r for r in rows if r["kind"] == "supported"]
    negatives = [r for r in rows if r["kind"] == "unsupported"]
    return {
        "supported_total": len(positives),
        "supported_correct": sum(
            r["prediction"] == r["expected_operation"] for r in positives
        ),
        "supported_wrong": sum(
            r["prediction"] not in (None, r["expected_operation"]) for r in positives
        ),
        "supported_refused": sum(r["prediction"] is None for r in positives),
        "unsupported_total": len(negatives),
        "unsupported_false_accepted": sum(
            r["prediction"] is not None for r in negatives
        ),
        "latency_ms_p50": round(percentile([r["latency_ms"] for r in rows], 50), 6),
        "latency_ms_p95": round(percentile([r["latency_ms"] for r in rows], 95), 6),
    }


def evaluate(
    route: PREDICTOR, cases: list[dict[str, Any]],
) -> dict[str, Any]:
    if not callable(route):
        raise ValueError("candidate must expose callable route(query)")
    if not cases:
        raise ValueError("no evaluation cases")
    rows = []
    ids: set[str] = set()
    for item in cases:
        case_id = item["id"]
        language = item["language"]
        if (not isinstance(case_id, str) or case_id in ids
            or language not in ("en", "ko", "ja")
            or item["kind"] not in ("supported", "unsupported")):
            raise ValueError("invalid case identity or cohort")
        ids.add(case_id)
        started = time.perf_counter()
        prediction = route(item["query"])
        elapsed = (time.perf_counter() - started) * 1000
        if prediction is not None and (
            type(prediction) is not str or prediction not in KINDS
        ):
            raise ValueError("candidate emitted out-of-vocabulary operation")
        rows.append({
            "case_id": case_id,
            "language": language,
            "kind": item["kind"],
            "expected_operation": item["expected_operation"],
            "prediction": prediction,
            "latency_ms": round(elapsed, 6),
        })
    global_metrics = summary(rows)
    if (
        len(rows) != 72
        or global_metrics["supported_total"] != 54
        or global_metrics["unsupported_total"] != 18
    ):
        raise ValueError("evaluation requires the exact 72-case DEV cohort")
    by_language = {
        lang: summary([r for r in rows if r["language"] == lang])
        for lang in ("en", "ko", "ja")
    }
    for lang, metrics in by_language.items():
        if (metrics["supported_total"], metrics["unsupported_total"]) != (18, 6):
            raise ValueError(f"malformed {lang} cohort")
    return {"rows": rows, "metrics": global_metrics, "by_language": by_language}


def measure(candidate: Path = CANDIDATE) -> dict[str, Any]:
    _, corpus, source_sha = load_inputs()
    if source_sha != CORPUS_SHA:
        raise ValueError("protected source digest drift")
    candidate_sha = digest(candidate)
    scorer_sha = digest(Path(__file__))
    loaded = runpy.run_path(str(candidate), run_name="__autoresearch_candidate__")
    result = evaluate(loaded.get("route"), corpus["cases"])
    if digest(candidate) != candidate_sha or digest(Path(__file__)) != scorer_sha:
        raise ValueError("candidate or evaluator mutated during scoring")
    return {
        "schema_version": 1,
        "status": "DEV_MEASURED_NOT_INDEPENDENT",
        "source_class": REPORT_CLASS,
        "corpus_sha256": source_sha,
        "candidate_sha256": candidate_sha,
        "evaluator_sha256": scorer_sha,
        "hardware_class": f"{platform.system()}/{platform.machine()}",
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "summary": result["metrics"],
        "by_language": result["by_language"],
        "rows": result["rows"],
        "tool_calls": 0,
        "may_grant_execution": False,
        "independent_qualification": False,
        "may_promote_to_product": False,
        "may_release": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, default=CANDIDATE)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = measure(args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "supported_correct": report["summary"]["supported_correct"],
        "supported_total": report["summary"]["supported_total"],
        "unsupported_false_accepted":
            report["summary"]["unsupported_false_accepted"],
        "p95_ms": report["summary"]["latency_ms_p95"],
        "may_promote_to_product": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

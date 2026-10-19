"""Frozen public BFCL V4 LIVE cross-encoder fit/no-fit diagnostic (E1 only).

Original public publisher sources and disjoint odd irrelevance calibration IDs.
No host/tool execution, no default routing, no release qualification.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from scripts.research_bfcl_pair_fit_live_transfer_e1 import (
    LIVE_BLOBS,
    fixed_fpr_cutoff,
    load_live_source,
    parse_task,
)
from scripts.research_bfcl_v4_public_relevance_e1 import (
    BFCL_COMMIT,
    _source_text,
    fetch_original_data,
)

MODEL_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
MODEL_REVISION = "c5ee24cb16019beea0893ab7796b1df96625c6b8"
STUDY = "PUBLIC_BFCL_V4_CPU_CROSS_ENCODER_NO_FIT_E1_EXPOSED_NOT_E2"
MAX_TOTAL_PAIRS = 100_000
BINS = ("1", "2-4", "5-12", "13+")


def menu_bin(size: int) -> str:
    if size < 1:
        raise ValueError("nonempty menus required for fitted-score bins")
    if size == 1:
        return "1"
    if size <= 4:
        return "2-4"
    if size <= 12:
        return "5-12"
    return "13+"


def score_one(
    record: dict[str, Any], model: Any,
) -> tuple[float | None, int, float]:
    """Only publisher final-user query and offered function contracts enter model."""
    query, functions = parse_task(record)
    if not functions:
        return None, 0, 0.0
    pairs = [(query, _source_text(fn)) for fn in functions]
    if any(not doc.strip() or len(doc) > 12_000 for _, doc in pairs):
        raise ValueError("original source contract outside model input limits")
    before = time.perf_counter()
    predicted = model.predict(
        pairs, batch_size=16, show_progress_bar=False,
    )
    duration = time.perf_counter() - before
    if len(predicted) != len(pairs):
        raise ValueError("model result length is not the source menu size")
    values = [float(score) for score in predicted]
    if any(not math.isfinite(score) for score in values):
        raise ValueError("nonfinite cross-encoder output")
    return max(values), len(functions), duration


def stats(scores: list[float], cutoff: float, *, supported: bool) -> dict[str, int]:
    accepted = sum(s >= cutoff for s in scores)
    result = {"total": len(scores), "accepted": accepted, "refused": len(scores) - accepted}
    if supported:
        result["false_refused"] = len(scores) - accepted
    else:
        result["false_accepted"] = accepted
    return result


def run(
    training: dict[str, list[dict[str, Any]]],
    live: dict[str, list[dict[str, Any]]],
    model: Any,
) -> dict[str, Any]:
    """Fixed splits, no threshold selection using LIVE category outcomes."""
    odds: list[float] = []
    total_pairs = 0
    elapsed_model_s = 0.0
    for row in training["irrelevance"]:
        ident = row.get("id")
        if type(ident) is not str or not ident.startswith("irrelevance_"):
            raise ValueError("source irrelevance cohort identity invalid")
        try:
            idx = int(ident[len("irrelevance_"):])
        except ValueError as exc:
            raise ValueError("source irrelevance cohort ID not numeric") from exc
        if not 0 <= idx < 240:
            raise ValueError("publisher irrelevance cohort ID out of range")
        if idx % 2 == 0:
            continue  # NEVER train or calibrate from even-ID records in this study.
        fit, width, duration = score_one(row, model)
        if fit is None:
            raise ValueError("odd calibration negative has an empty offered menu")
        odds.append(fit)
        total_pairs += width
        elapsed_model_s += duration
    if len(odds) != 120:
        raise ValueError("BFCL publisher original odd-ID calibration is not 120")
    cutoff = fixed_fpr_cutoff(odds)

    if len(live["live_relevance"]) != 16 or len(live["live_irrelevance"]) != 884:
        raise ValueError("pinned publisher LIVE split cardinality changed")
    buckets: dict[str, dict[str, list[float]]] = {
        kind: {group: [] for group in BINS}
        for kind in ("live_relevance", "live_irrelevance")
    }
    zero_menus = 0
    for kind in ("live_relevance", "live_irrelevance"):
        for row in live[kind]:
            fit, width, duration = score_one(row, model)
            if fit is None:
                if kind != "live_irrelevance":
                    raise ValueError("publisher positive case has an empty menu")
                zero_menus += 1
                continue
            buckets[kind][menu_bin(width)].append(fit)
            total_pairs += width
            elapsed_model_s += duration
            if total_pairs > MAX_TOTAL_PAIRS:
                raise ValueError("source menus exceed bounded CPU research study")

    pos = [x for group in BINS for x in buckets["live_relevance"][group]]
    neg = [x for group in BINS for x in buckets["live_irrelevance"][group]]
    if len(pos) != 16 or len(neg) != 880 or zero_menus != 4:
        raise ValueError("publisher LIVE positive/negative denominator drift")
    calibration_fpr = sum(x >= cutoff for x in odds)
    if calibration_fpr > 12:
        raise ValueError("predeclared <=10% odd calibration false admission violated")

    bin_results = {
        group: {
            "supported": stats(buckets["live_relevance"][group], cutoff, supported=True),
            "unsupported": stats(buckets["live_irrelevance"][group], cutoff, supported=False),
        }
        for group in BINS
    }
    return {
        "study": STUDY,
        "publisher_commit": BFCL_COMMIT,
        "original_live_blobs": {name: blob for name, (_, blob) in LIVE_BLOBS.items()},
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "split": {
            "calibrate_publisher_irrelevance_odd_ids": len(odds),
            "calibrate_false_accepted": calibration_fpr,
            "calibrate_budget_false_accepted": 12,
            "live_supported": len(pos),
            "live_unsupported_scored": len(neg),
            "live_unsupported_empty_menu_safe_excluded": zero_menus,
        },
        "calibration_max_score_threshold": cutoff,
        "live": {
            "supported": stats(pos, cutoff, supported=True),
            "unsupported": stats(neg, cutoff, supported=False),
            "original_menu_size_bins": bin_results,
        },
        "cpu_inference": {
            "offered_function_pairs_scored": total_pairs,
            "model_predict_seconds": round(elapsed_model_s, 3),
        },
        "public_model_training_contamination_possible": True,
        "heldout_independent_e2": False,
        "original_provider_or_agent_calls": False,
        "source_bfcl_live_category_seen_in_prior_studies": True,
        "default_product_changed": False,
        "release_qualified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    training, training_hashes = fetch_original_data()
    live, live_hashes = load_live_source()

    import resource

    import torch
    from sentence_transformers import CrossEncoder

    torch.set_num_threads(4)
    clock = time.perf_counter()
    model = CrossEncoder(
        MODEL_ID,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        device="cpu",
        max_length=512,
    )
    loaded_s = time.perf_counter() - clock
    results = run(training, live, model)
    results["publisher_sha256"] = {**training_hashes, **live_hashes}
    results["cpu_inference"]["model_load_seconds"] = round(loaded_s, 3)
    results["cpu_inference"]["wall_seconds_from_model_init"] = round(
        time.perf_counter() - clock, 3,
    )
    results["cpu_inference"]["max_rss_kib_linux"] = resource.getrusage(
        resource.RUSAGE_SELF,
    ).ru_maxrss
    results["cpu_inference"]["torch_threads"] = torch.get_num_threads()
    results["github_run_id"] = os.environ.get("GITHUB_RUN_ID")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": results["study"],
        "live": results["live"],
        "split": results["split"],
        "wall_seconds": results["cpu_inference"]["wall_seconds_from_model_init"],
        "max_rss_kib_linux": results["cpu_inference"]["max_rss_kib_linux"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

"""Actual CPU cross-encoder vs original PUBLIC BFCL function-fit / no-fit E1.

Do not promote to native G5, publisher-independent E2 or provider tool success.
Gold is NEVER a model input. Historical original E5+pair-fit baselines remain
unchanged; this is a new source-pinned, single-model diagnostic only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import time
from collections.abc import Callable
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
STUDY = "PUBLIC_BFCL_V4_CPU_CROSS_ENCODER_SINGLETON_NOFIT_E1_DEV"
BATCH = 32
MAX_CASES = 1400
MAX_PAIRS = 12000


def _size_bin(n: int) -> str:
    return "1" if n == 1 else "2-4" if n <= 4 else "5-12" if n <= 12 else "13+"


def score_original_cases(
    records: list[dict[str, Any]],
    predict: Callable[[list[tuple[str, str]]], Any],
) -> list[tuple[str, float | None, int]]:
    """Use original public user text and original function text, never task gold."""
    if type(records) is not list or len(records) > MAX_CASES:
        raise ValueError("bounded original publisher case list required")
    if not callable(predict):
        raise ValueError("real model predictor must be callable")
    pairs: list[tuple[str, str]] = []
    slots: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for row in records:
        if type(row) is not dict or type(row.get("id")) is not str:
            raise ValueError("original publisher case identity absent")
        ident = row["id"]
        if ident in seen:
            raise ValueError("duplicate original publisher case")
        seen.add(ident)
        query, offered = parse_task(row)
        start = len(pairs)
        for fn in offered:
            source = _source_text(fn)
            if not source.strip() or len(source) > 12000:
                raise ValueError("original function descriptor out of bounds")
            pairs.append((query, source))
            if len(pairs) > MAX_PAIRS:
                raise ValueError("original public BFCL pair budget exceeded")
        slots.append((ident, start, len(offered)))
    values: list[float] = []
    for at in range(0, len(pairs), BATCH):
        input_pairs = pairs[at:at + BATCH]
        predicted = predict(input_pairs)
        try:
            results = list(predicted)
            batch = [float(getattr(x, "item", lambda: x)()) for x in results]
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise ValueError("unverifiable original cross-encoder score") from exc
        if len(batch) != len(input_pairs) or any(
            not math.isfinite(score) for score in batch
        ):
            raise ValueError("cross-encoder output not a finite source pair score")
        values.extend(batch)
    if len(values) != len(pairs):
        raise ValueError("source-native candidate output length drift")
    return [
        (ident, max(values[start:start + size]) if size else None, size)
        for ident, start, size in slots
    ]


def run(
    training: dict[str, list[dict[str, Any]]],
    live: dict[str, list[dict[str, Any]]],
    predict: Callable[[list[tuple[str, str]]], Any],
) -> dict[str, Any]:
    """Calibrate only on source original odd IDs; evaluate PUBLIC live untouched."""
    if (
        set(training) != {"multiple", "irrelevance", "gold"}
        or set(live) != {"live_relevance", "live_irrelevance"}
        or len(training["multiple"]) != 200
        or len(training["irrelevance"]) != 240
        or len(live["live_relevance"]) != 16
        or len(live["live_irrelevance"]) > 1400
    ):
        raise ValueError("original public BFCL pinned cohort identity/size drift")
    chosen = {}
    for kind in ("multiple", "irrelevance"):
        source_rows = training[kind]
        qualified = []
        for row in source_rows:
            ident = row["id"]
            prefix = kind + "_"
            if type(ident) is not str or not ident.startswith(prefix):
                raise ValueError("malformed original BFCL calibration case ID")
            index = int(ident[len(prefix):])
            if index % 2 == 1:
                qualified.append(row)
        chosen[kind] = qualified
    if len(chosen["multiple"]) != 100 or len(chosen["irrelevance"]) != 120:
        raise ValueError("original publisher odd-ID calibration drift")
    negative = score_original_cases(chosen["irrelevance"], predict)
    if any(score is None for _, score, _ in negative):
        raise ValueError("original negative calibration has empty offered menu")
    negative_scores = [float(score) for _, score, _ in negative]
    threshold = fixed_fpr_cutoff(negative_scores)
    calibrated_positive = score_original_cases(chosen["multiple"], predict)
    if any(score is None for _, score, _ in calibrated_positive):
        raise ValueError("original positive calibration has empty offered menu")
    live_results: dict[str, dict[str, Any]] = {}
    for kind in ("live_relevance", "live_irrelevance"):
        scored = score_original_cases(live[kind], predict)
        admissions = 0
        withheld = 0
        zero_menu = 0
        bins: dict[str, dict[str, int]] = {}
        for _case_id, score, size in scored:
            if score is None:
                if kind != "live_irrelevance" or size != 0:
                    raise ValueError("publisher relevant function menu absent")
                zero_menu += 1
                continue
            allowed = score >= threshold
            admissions += int(allowed)
            withheld += int(not allowed)
            bucket = bins.setdefault(_size_bin(size), {
                "total": 0, "admitted": 0, "refused": 0,
            })
            bucket["total"] += 1
            bucket["admitted"] += int(allowed)
            bucket["refused"] += int(not allowed)
        live_results[kind] = {
            "original_publisher_total": len(scored),
            "offered_nonempty": admissions + withheld,
            "offered_empty_no_model_call": zero_menu,
            "admitted": admissions,
            "refused": withheld,
            "source_menu_size_bins": bins,
        }
    p = live_results["live_relevance"]
    n = live_results["live_irrelevance"]
    if p["offered_nonempty"] != 16 or n["offered_nonempty"] != 880 or (
        n["offered_empty_no_model_call"] != 4
    ):
        raise ValueError("original BFCL LIVE category denominator drift")
    pos_admit = sum(score is not None and score >= threshold
                    for _, score, _ in calibrated_positive)
    return {
        "study": STUDY,
        "external_original_public_e1_not_private": True,
        "publisher_commit": BFCL_COMMIT,
        "publisher_live_blobs": dict(LIVE_BLOBS),
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_training_changed": False,
        "calibration": {
            "positive_odd_id": 100,
            "negative_odd_id": 120,
            "target_negative_false_admit_fraction": 0.10,
            "negative_admitted": sum(x >= threshold for x in negative_scores),
            "positive_admitted": pos_admit,
            "model_logit_threshold": threshold,
        },
        "live_source": live_results,
        "observed_live_supported_admitted": p["admitted"],
        "observed_live_supported_false_refused": p["refused"],
        "observed_live_unsupported_false_accepted": n["admitted"],
        "observed_live_unsupported_safely_refused": n["refused"],
        "actual_native_provider_calls": 0,
        "independent_e2_qualified": False,
        "production_cutoff_calibrated": False,
        "default_product_changed": False,
        "release_qualified": False,
        "limitations": [
            "Publisher BFCL live category is already publicly exposed",
            "No full original function AST/argument accuracy or live invocations",
            "No original provider-independent EN/KO/JA E2 publisher gold",
            "English-only MS MARCO relevance model, not tool execution safety",
            "Odd-ID public calibration and LIVE category may be distribution-shifted",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    before = time.perf_counter()
    original, original_shas = fetch_original_data()
    live, live_shas = load_live_source()

    import torch
    from sentence_transformers import CrossEncoder

    torch.set_num_threads(4)
    model = CrossEncoder(
        MODEL_ID, revision=MODEL_REVISION,
        max_length=256, device="cpu", trust_remote_code=False,
    )
    def predict(pairs: list[tuple[str, str]]):
        return model.predict(
            pairs, batch_size=16, show_progress_bar=False,
        )
    report = run(original, live, predict)
    report["original_source_sha256"] = {**original_shas, **live_shas}
    report["elapsed_seconds_including_download"] = round(
        time.perf_counter() - before, 2,
    )
    report["peak_process_rss_kib_linux"] = resource.getrusage(
        resource.RUSAGE_SELF,
    ).ru_maxrss
    report["hardware"] = platform.platform()
    report["github_run_id"] = os.getenv("GITHUB_RUN_ID")
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], timeout=10, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": STUDY,
        "supported_admitted": report["observed_live_supported_admitted"],
        "supported_false_refused": report["observed_live_supported_false_refused"],
        "unsupported_false_accepted": report["observed_live_unsupported_false_accepted"],
        "unsupported_safely_refused": report["observed_live_unsupported_safely_refused"],
        "original_source_sha256": report["original_source_sha256"],
        "model_revision": report["model_revision"],
        "independent_e2_qualified": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

"""Real native Laya CHOICE / CHOICE+NOUL CPU development assessment.

No provider network API, no tool dispatch and no code path to construct an
execution authorization policy. Existing 72-example author-written corpus is
not a held-out validation surface. Both research arms are declared in advance.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from schemarouter import (  # noqa: E402
    DecisionOption,
    DecisionRequest,
    choose_sync,
)
from schemarouter.integrations import LayaDecisionBackend  # noqa: E402
from scripts.evaluate_operation_intent_cpu_dev import (  # noqa: E402
    DESCRIPTIONS,
    load_corpus,
    p95,
)

SOURCE_SHA256 = "18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7"
LAYA_VERSION = "0.4.7"
NOUL_RESEARCH_THRESHOLD = 0.5  # Fixed BEFORE scoring; NEVER operational calibration.
NOUL_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does the user affirmatively ask to perform exactly ONE operation "
        "among the listed actions? Answer NO for negated instructions, "
        "explanatory or how-to questions, multiple operations, or unrelated "
        "requests. Judge the original user request in its own language."
    ),
}


def safe_probability(value: Any, field: str) -> float:
    """Reject coerced strings, booleans and NaN instead of scoring them."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"invalid native Laya {field}")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"out-of-range native Laya {field}")
    return float(value)


def parse_native_pair(
    response: Any, allowed: set[str],
) -> tuple[str, float, float, str | None]:
    if not isinstance(response, dict):
        raise ValueError("native Laya response must be a mapping")
    answers = response.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("native Laya response missing answers")
    choice = answers.get("selection")
    veto = answers.get("one_action")
    if not isinstance(choice, dict) or choice.get("type") != "choice":
        raise ValueError("native Laya response lacks exact choice answer")
    if not isinstance(veto, dict) or veto.get("type") != "noul":
        raise ValueError("native Laya response lacks exact noul answer")
    selected = choice.get("choice")
    if type(selected) is not str or selected not in allowed:
        raise ValueError("native Laya returned unknown operation choice")
    confidence = safe_probability(choice.get("confidence"), "choice confidence")
    probability = safe_probability(veto.get("noul"), "noul probability")
    routing = response.get("routing")
    model = routing.get("model") if isinstance(routing, dict) else None
    if model is not None and not isinstance(model, str):
        raise ValueError("invalid routed model label")
    return selected, confidence, probability, model


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [r for r in rows if r["kind"] == "supported"]
    negative = [r for r in rows if r["kind"] == "unsupported"]
    if not positive or not negative:
        raise ValueError("both DEV cohorts are required")

    def metrics(group: list[dict[str, Any]]) -> dict[str, Any]:
        supported = [x for x in group if x["kind"] == "supported"]
        unsupported = [x for x in group if x["kind"] == "unsupported"]
        return {
            "supported": len(supported),
            "unsupported": len(unsupported),
            "correct_supported_rate": (
                sum(x["predicted"] == x["expected_operation"] for x in supported)
                / len(supported) if supported else None
            ),
            "wrong_supported_rate": (
                sum(x["predicted"] not in (None, x["expected_operation"])
                    for x in supported) / len(supported) if supported else None
            ),
            "supported_false_refusal_rate": (
                sum(x["predicted"] is None for x in supported) / len(supported)
                if supported else None
            ),
            "unsupported_false_accept_rate": (
                sum(x["predicted"] is not None for x in unsupported)
                / len(unsupported) if unsupported else None
            ),
            "latency_p50_ms": statistics.median(x["elapsed_ms"] for x in group),
            "latency_p95_ms": p95([x["elapsed_ms"] for x in group]),
        }

    return {
        "overall": metrics(rows),
        "by_language": {
            lang: metrics([r for r in rows if r["language"] == lang])
            for lang in sorted({r["language"] for r in rows})
        },
    }


def evaluate_with_router(
    router: Any,
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """The injectable router makes all scoring contracts testable offline."""
    choices = [
        DecisionOption(id=k, label=k, description=v)
        for k, v in DESCRIPTIONS.items()
    ]
    allowed = set(DESCRIPTIONS)
    backend = LayaDecisionBackend(router=router, device="cpu", min_confidence=0.0)
    choice_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    routed: dict[str, set[str]] = {"en": set(), "ko": set(), "ja": set()}
    for case in corpus["cases"]:
        request = DecisionRequest(
            query=case["query"], options=choices, max_selections=1,
        )
        start = time.perf_counter()
        original = choose_sync(backend, request)
        choice_ms = (time.perf_counter() - start) * 1000
        if original.abstained or len(original.selections) != 1:
            raise ValueError("unthresholded choice must yield a single known option")
        raw_selected = original.selections[0].option_id
        if raw_selected not in allowed:
            raise ValueError("unknown bounded Laya choice")
        questions = LayaDecisionBackend._questions(request)
        paired = {**questions, "one_action": dict(NOUL_QUESTION)}
        start = time.perf_counter()
        answer = router.predict({"query": case["query"]}, paired)
        pair_ms = (time.perf_counter() - start) * 1000
        selected, confidence, probability, route_model = parse_native_pair(
            answer, allowed,
        )
        if route_model is not None:
            routed[case["language"]].add(route_model)
        shared = {
            "case_id": case["id"],
            "language": case["language"],
            "kind": case["kind"],
            "expected_operation": case["expected_operation"],
        }
        choice_rows.append({
            **shared, "predicted": raw_selected,
            "elapsed_ms": round(choice_ms, 5),
            "choice_confidence": original.metadata.get("confidence"),
        })
        paired_rows.append({
            **shared,
            "predicted": (
                selected if probability >= NOUL_RESEARCH_THRESHOLD else None
            ),
            "raw_selected": selected,
            "choice_confidence": confidence,
            "noul_probability": probability,
            "noul_threshold_diagnostic_only": NOUL_RESEARCH_THRESHOLD,
            "elapsed_ms": round(pair_ms, 5),
            "routed_model": route_model,
        })
    return {
        "choice": {"summary": summarize(choice_rows), "rows": choice_rows},
        "choice_plus_noul": {
            "summary": summarize(paired_rows), "rows": paired_rows,
        },
        "routed_models": {lang: sorted(value) for lang, value in routed.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus", type=Path,
        default=ROOT / "benchmarks/operation-intent-trilingual-dev-20261015.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/laya-operation-intent-dev/laya.json"),
    )
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    corpus, digest = load_corpus(args.corpus)
    if digest != SOURCE_SHA256:
        raise ValueError("previously published 72-query DEV corpus changed")
    if args.preflight:
        print(json.dumps({
            "cases": len(corpus["cases"]), "sha256": digest,
            "arms": ["choice", "choice_plus_noul"],
            "noul_diagnostic_threshold": NOUL_RESEARCH_THRESHOLD,
            "laya_version": LAYA_VERSION,
        }))
        return 0

    import resource
    from importlib.metadata import version

    import torch
    from laya import Router

    if version("laya") != LAYA_VERSION:
        raise RuntimeError("Laya version drift")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    start = time.perf_counter()
    router = Router(device="cpu", max_loaded=1, preload=False)
    result = evaluate_with_router(router, corpus)
    total_ms = (time.perf_counter() - start) * 1000
    payload = {
        "surface": "prospective_operation_intent_development_only",
        "frozen_v014_untouched": True,
        "independent_validation": False,
        "no_tool_execution": True,
        "grants_execution_permission": False,
        "noul_threshold_calibrated": False,
        "experiment": "new 9-operation typed choice and combined choice+noul",
        "laya_version": version("laya"),
        "laya_checkpoint_selection": "native routed English/multilingual",
        "requested_device": "cpu",
        "actual_checkpoint_device_not_attested": True,
        "cpu_threads": torch.get_num_threads(),
        "model_weights_revision": "runtime-managed: inspect HF snapshot/cache",
        "source_corpus_sha256": digest,
        "elapsed_wall_ms_including_load": round(total_ms, 2),
        "peak_process_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
        ),
        "python": platform.python_version(),
        "results": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for arm in ("choice", "choice_plus_noul"):
        print(json.dumps({
            "arm": arm,
            "model": "Laya native (actual local checkpoint)",
            "summary": result[arm]["summary"]["overall"],
            "source_corpus_sha256": digest,
            "caution": "self-authored DEV, threshold uncalibrated, no execution",
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

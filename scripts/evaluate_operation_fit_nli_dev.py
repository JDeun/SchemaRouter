"""Pinned CPU multilingual NLI DEV arm, never an execution authorization.

The supplied user text is the premise; all nine locked English operation
hypotheses are scored with entailment probability. Threshold 0.70 is fixed
diagnostic-only. No new examples, automatic calibration, model training,
or access to existing frozen v0.14 heldout cases.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.research_operation_fit_conveyor import (  # noqa: E402
    KINDS,
    NLI_REVISION,
    load_inputs,
)

MODEL_ID = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
DIAGNOSTIC_THRESHOLD = 0.70
HYPOTHESES = {
    "search": "The user requests a search to find matching records.",
    "lookup": "The user requests to retrieve one existing record.",
    "list": "The user requests a list of registered entries.",
    "history": "The user requests a record of previous events or transactions.",
    "convert": "The user requests a currency or unit conversion.",
    "directions": "The user requests navigation directions.",
    "create": "The user requests to create a new record.",
    "update": "The user requests to update an existing record.",
    "delete": "The user requests to delete an existing record.",
}
if tuple(HYPOTHESES) != KINDS:
    raise RuntimeError("NLI premise hypotheses differ from frozen operation kinds")


def choose(scores: dict[str, float], *, gated: bool) -> str | None:
    if set(scores) != set(KINDS):
        raise ValueError("NLI must score exactly nine operation hypotheses")
    if any(
        type(value) not in (float, int)
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in scores.values()
    ):
        raise ValueError("invalid NLI entailment probability")
    ranked = sorted(KINDS, key=lambda name: (-scores[name], name))
    winner = ranked[0]
    return winner if not gated or scores[winner] >= DIAGNOSTIC_THRESHOLD else None


def evaluate(
    corpus: dict[str, Any],
    digest: str,
    *,
    scorer: Any,
) -> dict[str, Any]:
    arms: dict[str, list[dict[str, Any]]] = {
        "nli_forced": [], "nli_diagnostic_gate": [],
    }
    for case in corpus["cases"]:
        start = time.perf_counter()
        scores = scorer(case["query"])
        elapsed = round((time.perf_counter() - start) * 1000, 5)
        for name in arms:
            predicted = choose(scores, gated=name == "nli_diagnostic_gate")
            arms[name].append({
                "case_id": case["id"],
                "language": case["language"],
                "kind": case["kind"],
                "expected_operation": case["expected_operation"],
                "predicted_operation": predicted,
                "abstained": predicted is None,
                "top_similarity": max(scores.values()),
                "nli_entailment_scores": scores,
                "latency_ms": elapsed,
            })
    return {
        name: {
            "corpus_sha256": digest,
            "independent_validation": False,
            "grants_execution_authority": False,
            "rows": rows,
        }
        for name, rows in arms.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    plan, corpus, digest = load_inputs()
    assert plan["candidates"][1]["revision"] == NLI_REVISION
    if args.preflight:
        print(json.dumps({
            "cases": len(corpus["cases"]), "source_sha256": digest,
            "model_id": MODEL_ID, "revision": NLI_REVISION,
            "threshold": DIAGNOSTIC_THRESHOLD,
            "no_training": True, "no_tool_execution": True,
        }))
        return 0

    import resource

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, revision=NLI_REVISION, trust_remote_code=False,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, revision=NLI_REVISION, trust_remote_code=False,
        use_safetensors=True,
    )
    model.to("cpu")
    model.eval()
    labels = {str(name).lower(): int(index)
              for index, name in model.config.id2label.items()}
    if set(labels) != {"entailment", "neutral", "contradiction"}:
        raise RuntimeError("NLI model label order cannot be verified")
    entailment_idx = labels["entailment"]

    def score(query: str) -> dict[str, float]:
        encoded = tokenizer(
            [query] * len(KINDS), list(HYPOTHESES.values()),
            padding=True, truncation=True, max_length=256,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(**encoded).logits
        if tuple(logits.shape) != (len(KINDS), 3):
            raise RuntimeError("unexpected NLI logits shape")
        probabilities = torch.softmax(logits, dim=-1)[:, entailment_idx].tolist()
        scores = dict(zip(KINDS, (float(x) for x in probabilities), strict=True))
        if any(not math.isfinite(x) for x in scores.values()):
            raise RuntimeError("nonfinite CPU NLI output")
        return scores

    arms = evaluate(corpus, digest, scorer=score)
    result = {
        "model_key": "multilingual_nli",
        "model_id": MODEL_ID,
        "model_revision": NLI_REVISION,
        "model_weight_hash_attested": False,
        "threshold_calibrated": False,
        "independent_validation": False,
        "grants_execution_authority": False,
        "no_tool_execution": True,
        "corpus_sha256": digest,
        "nli_hypothesis_format": "user_query_premise_en_operation_hypotheses",
        "diagnostic_entailment_threshold": DIAGNOSTIC_THRESHOLD,
        "cpu_threads": torch.get_num_threads(),
        "peak_process_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2,
        ),
        "python": platform.python_version(),
        "wall_ms_including_load": round((time.perf_counter() - start) * 1000, 2),
        "arms": arms,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "model": MODEL_ID,
        "source_sha256": digest,
        "supported": 54, "unsupported": 18,
        "recorded_arms": list(arms),
        "note": "DEV diagnostic ONLY. No threshold/authorization promotion.",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

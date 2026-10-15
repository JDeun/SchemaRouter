"""Bounded recurring multilingual operation-intent DEV research loop.

Registered trial -> measured failure -> select next registered trial -> repeat.
Only an allowlisted fixed NLI checkpoint and DEV corpus are used. No code
changes, independent qualification, tools, deployments, or release authority.
Issue comments carry a validated resume cursor, NEVER a trusted authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from schemarouter import infer_operation_intent  # noqa: E402
from scripts.research_operation_fit_conveyor import (  # noqa: E402
    CORPUS_SHA,
    KINDS,
    NLI_REVISION,
    load_inputs,
)

MODEL_ID = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
PLAN = ROOT / "benchmarks/operation-fit-auto-loop-v1-plan.json"
VARIANTS = (
    "language_aligned_entailment",
    "signed_entailment_minus_contradiction",
    "signed_plus_lexical_negative_veto",
)
STATE_MARKER = "<!-- schemarouter-opfit-autoloop-v1:"
STATE_END = " -->"
BUDGET_PER_RUN = 2

# Human-authored variants in already observed DEV settings. These sentences
# were written AFTER initial NLI failure. Never call this a held-out test.
HYPOTHESES = {
    "en": (
        "The user requests a search to find matching records.",
        "The user requests to retrieve one existing record.",
        "The user requests a list of registered entries.",
        "The user requests a record of previous events or transactions.",
        "The user requests a currency or unit conversion.",
        "The user requests navigation directions.",
        "The user requests to create a new record.",
        "The user requests to update an existing record.",
        "The user requests to delete an existing record.",
    ),
    "ko": (
        "사용자는 조건에 맞는 기록을 검색해 달라고 요청합니다.",
        "사용자는 기존 기록 한 건을 조회해 달라고 요청합니다.",
        "사용자는 등록된 항목의 목록을 요청합니다.",
        "사용자는 과거 사건이나 거래 내역을 요청합니다.",
        "사용자는 통화나 단위의 변환을 요청합니다.",
        "사용자는 길 안내와 경로를 요청합니다.",
        "사용자는 새로운 기록의 생성을 요청합니다.",
        "사용자는 기존 기록을 수정해 달라고 요청합니다.",
        "사용자는 기존 기록을 삭제해 달라고 요청합니다.",
    ),
    "ja": (
        "利用者は条件に合う記録の検索を依頼しています。",
        "利用者は既存の記録一件の照会を依頼しています。",
        "利用者は登録済み項目の一覧を依頼しています。",
        "利用者は過去の出来事や取引履歴を求めています。",
        "利用者は通貨や単位の換算を依頼しています。",
        "利用者は目的地への道順を求めています。",
        "利用者は新しい記録の作成を依頼しています。",
        "利用者は既存の記録の更新を依頼しています。",
        "利用者は既存の記録の削除を依頼しています。",
    ),
}


def protocol() -> tuple[dict[str, Any], dict[str, Any], str]:
    underlying_plan, corpus, digest = load_inputs()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if (
        type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("id") != "operation-fit-recurring-dev-loop-v1"
        or plan.get("status") != "development_iteration_only"
        or plan.get("source_sha256") != CORPUS_SHA
        or plan.get("corpus") != underlying_plan["source"]["corpus"]
        or plan.get("model_id") != MODEL_ID
        or plan.get("model_revision") != NLI_REVISION
        or plan.get("per_run_budget") != BUDGET_PER_RUN
        or plan.get("maximum_total_variants") != len(VARIANTS)
        or plan.get("schedule_policy") != "weekly_main_only_and_manual"
        or plan.get("issue_tracker") != 1405
        or plan.get("independent_evaluation_approved") is not False
        or plan.get("model_training_enabled") is not False
        or plan.get("automatic_source_code_changes") is not False
        or plan.get("automatic_pr_merges") is not False
        or plan.get("developer_claims_not_independent") is not True
        or plan.get("release_policy") != "no_release_or_product_promotion"
        or plan.get("issues_policy") !=
        "only newly generated scoped AutoLab measurement issues may be auto-closed"
    ):
        raise ValueError("loop plan escalation or model/source drift")
    registered = plan.get("variants")
    if (
        not isinstance(registered, list)
        or [row.get("id") for row in registered] != list(VARIANTS)
        or [row.get("diagnostic_cutoff") for row in registered] != [
            0.7, 0.25, 0.25,
        ]
        or [row.get("execution") for row in registered] != [
            "language_matched_nli", "signed_nli", "signed_with_lexical_veto",
        ]
    ):
        raise ValueError("unapproved loop experiment registration")
    if (
        tuple(HYPOTHESES) != ("en", "ko", "ja")
        or any(len(phrases) != len(KINDS) for phrases in HYPOTHESES.values())
    ):
        raise ValueError("invalid trilingual operation hypotheses")
    return plan, corpus, digest


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_sha256": CORPUS_SHA,
        "model_revision": NLI_REVISION,
        "results": [],
        "independent_qualification": False,
        "may_promote_to_product": False,
        "may_merge_release": False,
    }


def validate_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != set(empty_state()):
        raise ValueError("unrecognized or incomplete persisted loop state")
    expected = empty_state()
    for key in expected:
        if key == "results":
            continue
        if state[key] != expected[key] or type(state[key]) is not type(expected[key]):
            raise ValueError("persisted loop state attempts identity/authority drift")
    results = state["results"]
    if not isinstance(results, list) or len(results) > len(VARIANTS):
        raise ValueError("invalid persisted trial results")
    seen: set[str] = set()
    for entry in results:
        if not isinstance(entry, dict) or set(entry) != {
            "variant", "supported_correct", "supported_wrong",
            "supported_refused", "unsupported_false_accepted",
            "dominant_fraction", "run_id",
        }:
            raise ValueError("invalid trial result schema")
        variant = entry["variant"]
        if variant not in VARIANTS or variant in seen:
            raise ValueError("unknown or duplicate trial in cursor")
        seen.add(variant)
        if (
            any(type(entry[key]) is not int or entry[key] < 0 for key in (
                "supported_correct", "supported_wrong",
                "supported_refused", "unsupported_false_accepted", "run_id",
            ))
            or entry["run_id"] <= 0
            or entry["supported_correct"] + entry["supported_wrong"]
            + entry["supported_refused"] != 54
            or entry["unsupported_false_accepted"] > 18
            or type(entry["dominant_fraction"]) not in (int, float)
            or not math.isfinite(entry["dominant_fraction"])
            or not 0 <= entry["dominant_fraction"] <= 1
        ):
            raise ValueError("corrupted persisted trial metric")
    return state


def parse_comments(comments: Any) -> dict[str, Any]:
    if not isinstance(comments, list):
        raise ValueError("GitHub comments payload must be a list")
    states = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        for line in body.splitlines():
            if line.startswith(STATE_MARKER) and line.endswith(STATE_END):
                payload = line[len(STATE_MARKER):-len(STATE_END)]
                states.append(validate_state(json.loads(payload)))
    return states[-1] if states else empty_state()


def next_variant(state: dict[str, Any]) -> str | None:
    validate_state(state)
    tried = {x["variant"] for x in state["results"]}
    remaining = [name for name in VARIANTS if name not in tried]
    if not remaining:
        return None
    recent = state["results"][-1] if state["results"] else {
        "dominant_fraction": 50 / 72,
        "unsupported_false_accepted": 4,
    }
    if (
        recent["dominant_fraction"] >= 0.5
        and "language_aligned_entailment" in remaining
    ):
        return "language_aligned_entailment"
    if (
        recent["unsupported_false_accepted"] > 0
        and "signed_entailment_minus_contradiction" in remaining
    ):
        return "signed_entailment_minus_contradiction"
    return remaining[0]


def choose_prediction(
    query: str,
    entailment: dict[str, float],
    contradiction: dict[str, float],
    variant: str,
) -> str | None:
    if variant not in VARIANTS:
        raise ValueError("unregistered experiment")
    if set(entailment) != set(KINDS) or set(contradiction) != set(KINDS):
        raise ValueError("missing action scores")
    if any(
        type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
        for x in (*entailment.values(), *contradiction.values())
    ):
        raise ValueError("nonfinite or nonprobabilistic NLI scores")
    signed = variant != "language_aligned_entailment"
    scores = {
        k: entailment[k] - contradiction[k] if signed else entailment[k]
        for k in KINDS
    }
    winner = sorted(KINDS, key=lambda kind: (-scores[kind], kind))[0]
    cutoff = 0.25 if signed else 0.7
    if scores[winner] < cutoff:
        return None
    if variant == "signed_plus_lexical_negative_veto":
        lex = infer_operation_intent(query)
        if lex.abstained or lex.operation != winner:
            return None
    return winner


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [x for x in rows if x["kind"] == "supported"]
    negatives = [x for x in rows if x["kind"] == "unsupported"]
    if len(positives) != 54 or len(negatives) != 18:
        raise ValueError("must score every supported and unsupported case")
    predictions = Counter(x["predicted_operation"] for x in rows)
    majority = max(KINDS, key=lambda k: predictions[k])
    summary = {
        "supported_correct": sum(
            x["predicted_operation"] == x["expected_operation"]
            for x in positives
        ),
        "supported_wrong": sum(
            x["predicted_operation"] not in (None, x["expected_operation"])
            for x in positives
        ),
        "supported_refused": sum(
            x["predicted_operation"] is None for x in positives
        ),
        "unsupported_false_accepted": sum(
            x["predicted_operation"] is not None for x in negatives
        ),
        "dominant_operation": majority,
        "dominant_fraction": predictions[majority] / len(rows),
        "by_language": {},
    }
    for lang in ("en", "ko", "ja"):
        part = [x for x in rows if x["language"] == lang]
        ps = [x for x in part if x["kind"] == "supported"]
        ns = [x for x in part if x["kind"] == "unsupported"]
        if len(ps) != 18 or len(ns) != 6:
            raise ValueError("invalid language-level cohort")
        summary["by_language"][lang] = {
            "supported_correct": sum(
                x["predicted_operation"] == x["expected_operation"] for x in ps
            ),
            "supported_refused": sum(
                x["predicted_operation"] is None for x in ps
            ),
            "unsupported_false_accepted": sum(
                x["predicted_operation"] is not None for x in ns
            ),
        }
    return summary


def evaluate_variant(
    variant: str,
    corpus: dict[str, Any],
    scorer: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant not in VARIANTS:
        raise ValueError("nonallowlisted experiment")
    rows = []
    for item in corpus["cases"]:
        started = time.perf_counter()
        entail, contradict = scorer(
            item["query"], HYPOTHESES[item["language"]],
        )
        result = choose_prediction(item["query"], entail, contradict, variant)
        rows.append({
            "case_id": item["id"],
            "language": item["language"],
            "kind": item["kind"],
            "expected_operation": item["expected_operation"],
            "predicted_operation": result,
            "latency_ms": round((time.perf_counter() - started) * 1000, 5),
        })
    return rows, metrics(rows)


def loop(
    state: dict[str, Any], corpus: dict[str, Any], scorer: Any,
    run_id: int,
) -> dict[str, Any]:
    state = validate_state(state)
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("valid GitHub Actions run ID required")
    working = json.loads(json.dumps(state))
    results = []
    for _ in range(BUDGET_PER_RUN):
        variant = next_variant(working)
        if variant is None:
            break
        rows, summary = evaluate_variant(variant, corpus, scorer)
        working["results"].append({
            "variant": variant,
            "supported_correct": summary["supported_correct"],
            "supported_wrong": summary["supported_wrong"],
            "supported_refused": summary["supported_refused"],
            "unsupported_false_accepted": summary["unsupported_false_accepted"],
            "dominant_fraction": summary["dominant_fraction"],
            "run_id": run_id,
        })
        results.append({
            "variant": variant,
            "metrics": summary,
            "rows": rows,
            "run_id": run_id,
        })
    return {
        "state": working,
        "new_results": results,
        "variants_exhausted": next_variant(working) is None,
        "status": "DEV_EVIDENCE_ONLY",
        "source_sha256": CORPUS_SHA,
        "model_revision": NLI_REVISION,
        "independent_validation": False,
        "may_promote_to_product": False,
        "may_merge_release": False,
        "may_execute_tools": False,
        "may_auto_merge_pr": False,
    }


def formatted_comment(report: dict[str, Any], run_url: str) -> str:
    state = validate_state(report["state"])
    new = report["new_results"]
    lines = [
        "### Operation-Fit AutoLab DEV research loop",
        "",
        f"Run: {run_url}",
        f"New measured variants: {len(new)}; completed total: {len(state['results'])}/3.",
        "All metrics are on the previously seen 72-item DEV corpus.",
        "No independent qualification, product change or release permission.",
        "",
    ]
    for item in new:
        stats = item["metrics"]
        lines.append(
            f"- `{item['variant']}`: supported correct "
            f"{stats['supported_correct']}/54, wrong "
            f"{stats['supported_wrong']}/54, false refusal "
            f"{stats['supported_refused']}/54, unsupported false accepted "
            f"{stats['unsupported_false_accepted']}/18."
        )
    if report["variants_exhausted"]:
        lines.append("All registered DEV variants exhausted. No further model runs.")
    lines.append("")
    # The bot-only marker is a strictly checked checkpoint, not authorization.
    compact = json.dumps(state, separators=(",", ":"), ensure_ascii=True)
    lines.append(f"{STATE_MARKER}{compact}{STATE_END}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("plan", "run", "comment"), required=True)
    parser.add_argument("--comments", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _, corpus, _ = protocol()
    if args.stage == "plan":
        if args.comments is None:
            parser.error("--comments is required for plan stage")
        state = parse_comments(json.loads(args.comments.read_text(encoding="utf-8")))
        result = {
            "state": state,
            "should_run": next_variant(state) is not None,
            "remaining": len(VARIANTS) - len(state["results"]),
        }
        if "GITHUB_OUTPUT" in os.environ:
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as f:
                f.write(f"should_run={str(result['should_run']).lower()}\n")
    elif args.stage == "run":
        if args.state is None:
            parser.error("--state is required for run stage")
        state_raw = json.loads(args.state.read_text(encoding="utf-8"))
        state = validate_state(state_raw["state"])
        if next_variant(state) is None:
            raise ValueError("already exhausted; do not download model")
        from importlib.metadata import version

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if not version("transformers"):
            raise RuntimeError("transformer runtime missing")
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID, revision=NLI_REVISION, trust_remote_code=False,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_ID, revision=NLI_REVISION, trust_remote_code=False,
            use_safetensors=True,
        ).to("cpu")
        model.eval()
        labels = {
            str(name).lower(): int(index)
            for index, name in model.config.id2label.items()
        }
        if set(labels) != {"entailment", "neutral", "contradiction"}:
            raise RuntimeError("NLI labels do not match expected")
        def real_scorer(
            query: str, hypotheses: tuple[str, ...],
        ) -> tuple[dict[str, float], dict[str, float]]:
            inputs = tokenizer(
                [query] * len(KINDS), list(hypotheses),
                padding=True, truncation=True, max_length=256,
                return_tensors="pt",
            )
            with torch.inference_mode():
                output = model(**inputs).logits
            if tuple(output.shape) != (9, 3):
                raise RuntimeError("unexpected NLI output dimensions")
            probs = torch.softmax(output, dim=-1).tolist()
            entail = {
                key: float(probs[i][labels["entailment"]])
                for i, key in enumerate(KINDS)
            }
            contradict = {
                key: float(probs[i][labels["contradiction"]])
                for i, key in enumerate(KINDS)
            }
            return entail, contradict
        result = loop(state, corpus, real_scorer, int(os.environ["GITHUB_RUN_ID"]))
        result["model_id"] = MODEL_ID
        result["python"] = platform.python_version()
        result["model_weights_sha256_attested"] = False
    else:
        if args.report is None:
            parser.error("--report required for comment")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        run_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        repo = os.environ.get("GITHUB_REPOSITORY", "JDeun/SchemaRouter")
        run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
        comment = formatted_comment(
            report, f"{run_url}/{repo}/actions/runs/{run_id}",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(comment, encoding="utf-8")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result.get("status", "PLAN"),
        "should_run": result.get("should_run"),
        "completed": len(result.get("state", {}).get("results", [])),
        "new_trials": len(result.get("new_results", [])),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

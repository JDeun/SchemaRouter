"""Counterfactual *oracle*-operation rerank of frozen multilingual DEV Top-10.

This does NOT learn a multilingual classifier or infer trusted user intent.
It asks only whether source-authored route operation declarations could have
disambiguated the ORIGINAL real MiniLM/E5 ranked candidate lists.  The
previously exposed gold route is used ONLY for evaluating the output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_multilingual_score_overlap_dev import (
    EXPECTED_CORPUS,
    LANGUAGES,
    MODELS,
    SIZES,
    _audit_rows,
    _check,
    _load,
    audit_reports,
)

# Explicit synthetic HOST SIMULATOR route contracts: these are not extracted
# from similarity scores, query IDs or users. No operation creates authority.
BASE_OPERATION = {
    "materials.search": "search",
    "materials.units": "lookup",
    "papers.search": "search",
    "papers.citations": "lookup",
    "weather.current": "lookup",
    "inventory.lookup": "lookup",
    "inventory.audit": "history",
    "flights.search": "search",
    "flights.status": "lookup",
    "finance.convert_currency": "convert",
    "finance.exchange_history": "history",
    "calendar.list_events": "list",
    "maps.directions": "directions",
}
# Generator's read-only operations do not imply live navigation, prediction,
# mutation or external execution; classify "routes" as record lookup.
GENERATOR_OPERATION = {
    "search": "search", "lookup": "lookup", "list": "list",
    "status": "lookup", "history": "history", "summary": "lookup",
    "compare": "lookup", "metadata": "lookup", "quality": "lookup",
    "audit": "history", "availability": "lookup", "forecast": "lookup",
    "measurements": "lookup", "citations": "lookup",
    "classification": "lookup", "constraints": "lookup",
    "routes": "lookup", "analytics": "lookup",
}
# These are manually authored *intent oracle* labels for the previously
# exposed source cases. DO NOT derive host operation from expected_route or
# treat these labels as measured user-intent classifier predictions.
CASE_INTENT = {
    "materials.search": "search",
    "papers.search": "search",
    "weather.current": "lookup",
    "inventory.lookup": "lookup",
    "flights.search": "search",
    "finance.convert_currency": "convert",
    "calendar.list_events": "list",
    "maps.directions": "directions",
    "materials.delete_sample": "delete",
    "papers.submit_paper": None,  # no trustworthy submitted-papers operation
    "inventory.adjust_stock": "update",
    "flights.book_ticket": "create",
    "finance.transfer_money": None,  # no trusted bank transfer operation
    "calendar.create_event": "create",
}
_ALLOWS = {"search", "lookup", "list", "history", "convert",
           "directions", "create", "update", "delete"}


def _intent_for_id(case_id: str, kind: str, language: str) -> str | None:
    prefix = f"{kind}-{language}-"
    _check(case_id.startswith(prefix), "unregistered oracle-intent cohort")
    family = case_id[len(prefix):]
    _check(family in CASE_INTENT, "unregistered author-DEV query intent")
    return CASE_INTENT[family]


def declared_route_operation(route_id: str) -> str | None:
    if route_id in BASE_OPERATION:
        return BASE_OPERATION[route_id]
    pieces = route_id.split(".")
    if len(pieces) != 3 or pieces[0] != "dev_stress":
        return None
    return GENERATOR_OPERATION.get(pieces[2])


def compatible_top10(ranked: list[str], intent: str | None) -> list[str]:
    """Trust only an externally supplied operation *simulation*.

    No gold labels, similarity thresholds, or model/agent calls are accepted.
    Missing operation MUST yield no shortlist.
    """
    if intent is None or intent not in _ALLOWS:
        return []
    return [
        route for route in ranked
        if declared_route_operation(route) == intent
    ]


def evaluate(
    models: dict[str, dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    original_audit = audit_reports(models, provenance=provenance)
    _check(set(BASE_OPERATION) == {
        "materials.search", "materials.units", "papers.search",
        "papers.citations", "weather.current", "inventory.lookup",
        "inventory.audit", "flights.search", "flights.status",
        "finance.convert_currency", "finance.exchange_history",
        "calendar.list_events", "maps.directions",
    }, "model catalogue's original 13 routes changed")
    _check(
        len(CASE_INTENT) == 14 and set(GENERATOR_OPERATION) ==
        {"search", "lookup", "list", "status", "history", "summary",
         "compare", "metadata", "quality", "audit", "availability",
         "forecast", "measurements", "citations", "classification",
         "constraints", "routes", "analytics"},
        "synthetic author-DEV route/intent contract changed",
    )
    summary: dict[str, dict[str, Any]] = {}
    paired_rows = []
    for model in MODELS:
        summary[model] = {}
        for size in SIZES:
            by_id = _audit_rows(models[model]["results"][size]["rows"])
            supported, unsupported = [], []
            for case_id, row in sorted(by_id.items()):
                intent = _intent_for_id(
                    case_id, row["kind"], row["language"],
                )
                options = compatible_top10(row["top_10"], intent)
                gold = row["expected_route"]
                baseline_hit = row["hit_at_1"] if gold is not None else None
                host_oracle_hit = (
                    options[0] == gold if options and gold is not None else False
                )
                entry = {
                    "case_id": case_id,
                    "model": model, "size": int(size),
                    "language": row["language"], "kind": row["kind"],
                    "source_top1": row["top_1"],
                    "declared_oracle_intent": intent,
                    "candidate_compatible_count": len(options),
                    "candidate_compatible_top1": options[0] if options else None,
                    "baseline_gold_top1": baseline_hit,
                    "gold_was_in_original_top10": (
                        gold in row["top_10"] if gold is not None else None
                    ),
                    "oracle_gold_top1": (
                        host_oracle_hit if gold is not None else None
                    ),
                    "oracle_abstained": not options,
                }
                paired_rows.append(entry)
                if gold is not None:
                    supported.append(entry)
                else:
                    unsupported.append(entry)
            _check(len(supported) == 48 and len(unsupported) == 36,
                   "wrong gold denominator")
            lost = [
                x["case_id"] for x in supported
                if x["gold_was_in_original_top10"]
                and not x["oracle_gold_top1"]
            ]
            raw_correct = sum(x["baseline_gold_top1"] for x in supported)
            oracle_correct = sum(x["oracle_gold_top1"] for x in supported)
            # A trustworthy declared operation cannot recover a target that
            # embedding recall omitted entirely from its original Top 10.
            impossible = sum(
                not x["gold_was_in_original_top10"] for x in supported
            )
            summary[model][size] = {
                "supported": 48, "unsupported": 36,
                "raw_model_top1_correct": raw_correct,
                "model_top10_recoverable": 48 - impossible,
                "oracle_operation_top1_correct": oracle_correct,
                "oracle_operation_false_refused_supported": sum(
                    x["oracle_abstained"] for x in supported
                ),
                "oracle_operation_wrong_supported": 48 - oracle_correct -
                    sum(x["oracle_abstained"] for x in supported),
                "unsupported_false_accept_with_oracle": sum(
                    not x["oracle_abstained"] for x in unsupported
                ),
                "unsupported_abstentions_with_oracle": sum(
                    x["oracle_abstained"] for x in unsupported
                ),
                "gold_in_original_top10_but_oracle_wrong_case_ids": lost,
                "by_language": {
                    lang: {
                        "supported": 8,
                        "raw_top1": sum(x["baseline_gold_top1"] for x in supported
                                        if x["language"] == lang),
                        "oracle_top1": sum(x["oracle_gold_top1"] for x in supported
                                           if x["language"] == lang),
                        "top10_recoverable": sum(
                            x["gold_was_in_original_top10"]
                            for x in supported if x["language"] == lang
                        ),
                        "unsupported": 6,
                        "oracle_false_accept": sum(
                            not x["oracle_abstained"]
                            for x in unsupported if x["language"] == lang
                        ),
                    } for lang in LANGUAGES
                },
            }
            _check(
                oracle_correct <= 48 - impossible,
                "oracle violates original candidate recall upper bound",
            )
    expected = 2 * 4 * 84
    _check(len(paired_rows) == expected, "incomplete model/scale DEV oracle")
    return {
        "schema_version": 1,
        "study": "author_visible_declared_operation_oracle_counterfactual",
        "source": original_audit["provenance"],
        "original_corpus_sha256": EXPECTED_CORPUS,
        "cases_actual": len(paired_rows),
        "cases_expected": expected,
        "summary": summary,
        "cases": paired_rows,
        "limitations": {
            "trusted_operation_labels_are_author_authored_oracle": True,
            "classifier_accuracy_measured": False,
            "data_seen_for_development": True,
            "counterfactual_reorders_existing_top10_only": True,
            "provider_authorization_or_host_identity": False,
            "real_tool_or_agent_executed": False,
            "independent_evaluation": False,
            "calibrated_no_fit_threshold": False,
            "may_select_default_or_release": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minilm", type=Path, required=True)
    ap.add_argument("--e5", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw = manifest["reports"]
    models = {
        "minilm": _load(args.minilm, raw["minilm"]["sha256"]),
        "e5-small": _load(args.e5, raw["e5-small"]["sha256"]),
    }
    result = evaluate(models, {
        key: manifest[key] for key in (
            "source_repository", "source_run_id",
            "head_sha", "independent_confirmation",
        )
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["study"],
        "cases": result["cases_actual"],
        "summary_500": {
            model: result["summary"][model]["500"]
            for model in MODELS
        },
        "independent": False,
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

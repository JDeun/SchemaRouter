"""Registry inventory and reproducible improvement-opportunity analysis.

Historical experiments are REFERENCES ONLY. Never rerun prior models, pool
incomparable cohorts, or infer independent improvement from development errors.
Only two same-run, row-provenance-audited reports are compared case by case.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research_operation_fit_conveyor import (  # noqa: E402
    CORPUS_SHA,
    KINDS,
    _metric_rows,
    load_inputs,
)

REGISTRY = ROOT / "benchmarks/operation-fit-conveyor-v1-registry.json"
ALLOWED_STATUS = {
    "active_stage", "completed_reference",
    "incomparable_frozen_reference", "blocked",
}
ALLOWED_TIERS = {
    "current_dev", "prior_dev_same_corpus", "legacy_different_cohort",
    "future_independent", "future_training", "future_paid",
}
EXPECTED_IDS = (
    "lexical_baseline",
    "multilingual_nli_forced_and_gate",
    "minilm_and_e5_prior",
    "laya_choice_and_noul_prior",
    "semantic_router_style_exemplars_prior",
    "retrieval_top3_crossencoder_prior",
    "bge_sibling_contrastive_010",
    "agent_utility_014",
    "new_query_disjoint_holdout",
    "authentic_tool_catalog_100_250_500",
    "small_supervised_operation_classifier",
    "hosted_jev",
    "real_agent_execution_no_call",
)


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or set(registry) != {
        "schema_version", "experiment", "cohort_sha256", "classification",
        "automatic_dispatch_enabled", "independent_qualification",
        "product_promotion", "allowed_active_ids", "entries",
    }:
        raise ValueError("registry schema drift")
    if (
        type(registry["schema_version"]) is not int
        or registry["schema_version"] != 1
        or registry["experiment"] != "operation-fit-conveyor-v1"
        or registry["cohort_sha256"] != CORPUS_SHA
        or registry["classification"] != "dev_research_index_not_execution_schedule"
        or registry["automatic_dispatch_enabled"] is not False
        or registry["independent_qualification"] is not False
        or registry["product_promotion"] is not False
        or registry["allowed_active_ids"] != list(EXPECTED_IDS[:2])
    ):
        raise ValueError("registry escalation or cohort revision")
    items = registry["entries"]
    if not isinstance(items, list) or [x.get("id") for x in items] != list(
        EXPECTED_IDS
    ):
        raise ValueError("unknown, duplicate, or reordered registry experiment")
    for pos, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {
            "id", "status", "tier", "workflow", "source_report",
            "run_id", "artifact_id", "corpus_sha256", "blocker",
        }:
            raise ValueError("registry row schema drift")
        if item["status"] not in ALLOWED_STATUS or item["tier"] not in ALLOWED_TIERS:
            raise ValueError("invalid registered experimental state")
        if pos < 2:
            if (
                item["status"] != "active_stage"
                or item["tier"] != "current_dev"
                or item["workflow"] != "research-operation-fit-conveyor-dev.yml"
                or item["corpus_sha256"] != CORPUS_SHA
                or any(item[k] is not None for k in (
                    "source_report", "run_id", "artifact_id", "blocker"
                ))
            ):
                raise ValueError("active study config drift")
        elif pos < 6:
            if (
                item["status"] != "completed_reference"
                or item["tier"] != "prior_dev_same_corpus"
                or item["corpus_sha256"] != CORPUS_SHA
                or type(item["run_id"]) is not int
                or item["run_id"] <= 0
                or type(item["artifact_id"]) is not int
                or item["artifact_id"] <= 0
                or item["workflow"] is not None
                or item["blocker"] is not None
            ):
                raise ValueError("historical evidence is not a dispatch stage")
            report = item["source_report"]
            if (
                not isinstance(report, str)
                or not report.startswith("benchmarks/")
                or not report.endswith(".md")
                or not (ROOT / report).is_file()
            ):
                raise ValueError("missing same-cohort research report")
        else:
            if (
                item["status"] not in (
                    {"incomparable_frozen_reference"} if pos < 8
                    else {"blocked"}
                )
                or item["corpus_sha256"] is not None
                or item["workflow"] is not None
                or item["source_report"] is not None and pos >= 8
                or not isinstance(item["blocker"], str)
                or not item["blocker"].strip()
            ):
                raise ValueError("unapproved historical/future experiment enabled")
    return registry


def compile_opportunities(
    baseline: dict[str, Any],
    nli: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan, corpus, digest = load_inputs()
    registry = load_registry() if registry is None else registry
    if registry["cohort_sha256"] != digest:
        raise ValueError("registry/corpus mismatch")
    if baseline.get("model_key") != "lexical_baseline":
        raise ValueError("invalid baseline identity")
    if (
        nli.get("model_key") != "multilingual_nli"
        or nli.get("model_id") != plan["candidates"][1]["model"]
        or nli.get("model_revision") != plan["candidates"][1]["revision"]
        or set(nli.get("arms", {})) != {
            "nli_forced", "nli_diagnostic_gate",
        }
        or nli.get("no_tool_execution") is not True
    ):
        raise ValueError("unapproved NLI evidence")
    arms = {
        "lexical_baseline": baseline,
        "nli_forced": nli["arms"]["nli_forced"],
        "nli_diagnostic_gate": nli["arms"]["nli_diagnostic_gate"],
    }
    # Exhaustively validate all three row sets against original labels/IDs.
    for name, report in arms.items():
        _metric_rows(report, corpus, digest, arm=name)
    rows = {
        name: {row["case_id"]: row for row in report["rows"]}
        for name, report in arms.items()
    }
    by_language: dict[str, Counter[str]] = {
        lang: Counter() for lang in ("en", "ko", "ja")
    }
    by_operation: dict[str, Counter[str]] = {kind: Counter() for kind in KINDS}
    failures: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        case_id = case["id"]
        lang = case["language"]
        label = case["expected_operation"]
        b = rows["lexical_baseline"][case_id]["predicted_operation"]
        f = rows["nli_forced"][case_id]["predicted_operation"]
        g = rows["nli_diagnostic_gate"][case_id]["predicted_operation"]
        if case["kind"] == "supported":
            status = (
                "both_correct" if b == label and f == label
                else "baseline_correct_nli_wrong"
                if b == label else "nli_correct_baseline_wrong"
                if f == label else "neither_correct"
            )
            by_language[lang][status] += 1
            by_operation[label][status] += 1
            if g is None:
                by_language[lang]["gated_supported_refused"] += 1
            if status != "both_correct" or g != label:
                failures.append({
                    "case_id": case_id,
                    "language": lang,
                    "cohort": "supported",
                    "expected_operation": label,
                    "baseline_prediction": b,
                    "nli_forced_prediction": f,
                    "nli_gated_prediction": g,
                    "error_type": status,
                })
        else:
            if b is not None:
                by_language[lang]["baseline_unsupported_false_accept"] += 1
            if f is not None:
                by_language[lang]["forced_unsupported_false_accept"] += 1
            if g is not None:
                by_language[lang]["gated_unsupported_false_accept"] += 1
                failures.append({
                    "case_id": case_id,
                    "language": lang,
                    "cohort": "unsupported",
                    "expected_operation": None,
                    "baseline_prediction": b,
                    "nli_forced_prediction": f,
                    "nli_gated_prediction": g,
                    "error_type": "gated_unsupported_false_accept",
                })
    contrast = {
        "by_language": {
            lang: dict(sorted(count.items()))
            for lang, count in by_language.items()
        },
        "by_operation": {
            kind: dict(sorted(count.items()))
            for kind, count in by_operation.items()
        },
        "case_level_failure_examples": failures,
        "investigation_count": len(failures),
    }
    # All research proposals are hypotheses, NOT empirically verified fixes.
    hypotheses = [
        {
            "id": "linguistic_premise_hypothesis_alignment",
            "justification": (
                "Inspect per-language error asymmetry from NLI English hypotheses"
            ),
            "next_evidence": (
                "Independently authored disjoint EN/KO/JA template contrast,"
                " with fixed translations and blinded adjudication"
            ),
            "status": "PROPOSED_UNAPPROVED_NO_AUTO_EXECUTION",
        },
        {
            "id": "contrastive_operation_specific_selector",
            "justification": (
                "Audit cases where a correct retrieved operation differs"
                " from forced NLI decision"
            ),
            "next_evidence": (
                "Frozen task-specific model, authorized training labels,"
                " independent scored negatives and 100/250/500 real tool schemas"
            ),
            "status": "PROPOSED_UNAPPROVED_NO_AUTO_EXECUTION",
        },
        {
            "id": "separate_explicit_negative_veto",
            "justification": (
                "Inspect unsupported false accepts without sacrificing"
                " supported operation recall"
            ),
            "next_evidence": (
                "Independent negation, compound and near-domain negatives;"
                " joint false-accept/false-refusal bounds"
            ),
            "status": "PROPOSED_UNAPPROVED_NO_AUTO_EXECUTION",
        },
    ]
    return {
        "schema_version": 1,
        "status": "DEVELOPMENT_ERROR_ANALYSIS_ONLY",
        "source_sha256": digest,
        "same_run_arms": sorted(arms),
        "historical_reference_only": [
            x["id"] for x in registry["entries"]
            if x["status"] == "completed_reference"
        ],
        "non_comparable_or_blocked": [
            {"id": x["id"], "reason": x["blocker"]}
            for x in registry["entries"]
            if x["status"] in {"incomparable_frozen_reference", "blocked"}
        ],
        "contrast": contrast,
        "improvement_hypotheses": hypotheses,
        "no_automatic_experiment_dispatch": True,
        "no_independent_qualification": True,
        "may_promote_to_product": False,
        "may_merge_release": False,
        "may_execute_tools": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-check", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--nli", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = load_registry()
    if args.registry_check:
        result = {
            "status": "EXPERIMENT_REGISTRY_VALID_NO_AUTOMATIC_DISPATCH",
            "experiments": len(registry["entries"]),
            "active_stages": len(registry["allowed_active_ids"]),
            "historical_only": sum(x["status"] == "completed_reference"
                                   for x in registry["entries"]),
            "blocked_or_incomparable": sum(
                x["status"] in {"blocked", "incomparable_frozen_reference"}
                for x in registry["entries"]
            ),
            "source_sha256": registry["cohort_sha256"],
        }
    else:
        if args.baseline is None or args.nli is None:
            parser.error("same-run baseline and NLI evidence required")
        result = compile_opportunities(
            json.loads(args.baseline.read_text(encoding="utf-8")),
            json.loads(args.nli.read_text(encoding="utf-8")),
            registry=registry,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: value for key, value in result.items()
        if key not in {"contrast", "improvement_hypotheses", "non_comparable_or_blocked"}
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

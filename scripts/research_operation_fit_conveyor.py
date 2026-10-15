"""Gated, non-promoting operation-fit DEV conveyor, separate from 0.14.

This controller is deterministic and offline: validates preregistration,
input SHA, cohorts, report provenance and negative cases; emits a DEV screen
with explicit blocks. It neither trains/executes tools nor grants release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "benchmarks/operation-fit-conveyor-v1-plan.json"
CORPUS_SHA = "18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7"
NLI_REVISION = "0a71e92a985b6e1ad1828cf67ce9c459639c1dca"
KINDS = (
    "search", "lookup", "list", "history", "convert",
    "directions", "create", "update", "delete",
)
ARMS = ("lexical_baseline", "nli_forced", "nli_diagnostic_gate")


def load_inputs(
    plan_path: Path = PLAN_PATH,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "id", "status", "frozen_v014_unchanged",
        "permitted_execution", "forbidden_execution", "source",
        "candidates", "decision", "external_confirmation",
    }
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError("conveyor plan keys differ from locked protocol")
    if (
        type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
        or plan["id"] != "operation-fit-conveyor-v1-dev"
        or plan["status"] != "prospective_development_only"
        or plan["frozen_v014_unchanged"] is not True
        or plan["permitted_execution"] != [
            "offline_preflight", "lexical_baseline",
            "multilingual_nli_cpu", "dev_aggregate",
        ]
        or plan["forbidden_execution"] != [
            "independent_holdout", "product_cutover",
            "model_training", "tool_dispatch",
        ]
    ):
        raise ValueError("conveyor stage authorization/provenance drift")
    src = plan["source"]
    if (
        src.get("corpus") !=
        "benchmarks/operation-intent-trilingual-dev-20261015.json"
        or src.get("sha256") != CORPUS_SHA
        or src.get("supported") != 54
        or src.get("unsupported") != 18
        or src.get("languages") != ["en", "ko", "ja"]
        or src.get("provenance") !=
        "previously_seen_author_written_development_examples"
    ):
        raise ValueError("unapproved corpus source/split")
    candidates = plan["candidates"]
    if not isinstance(candidates, list) or len(candidates) != 3:
        raise ValueError("conveyor requires exact three registered arms")
    if (
        candidates[0].get("id") != "lexical_baseline"
        or candidates[0].get("status") != "ready"
        or candidates[1].get("id") != "multilingual_nli"
        or candidates[1].get("model") !=
        "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
        or candidates[1].get("revision") != NLI_REVISION
        or candidates[1].get("status") != "ready_for_dev"
        or candidates[1].get("diagnostic_entailment_threshold") != 0.7
        or candidates[1].get("model_weight_hash_attested") is not False
        or candidates[2].get("id") != "task_specific_classifier"
        or candidates[2].get("status") !=
        "blocked_no_training_data_or_checkpoint"
        or candidates[2].get("model") is not None
    ):
        raise ValueError("candidate model/revision or blocked classifier drift")
    controls = plan["decision"]
    if (
        controls.get("source") != "development_screen_not_promotion"
        or controls.get("supported_correct_min") != 0.85
        or controls.get("unsupported_false_accept_max") != 0.05
        or controls.get("supported_false_refusal_max") != 0.1
        or controls.get("supported_wrong_operation_max") != 0.03
        or controls.get("p95_cpu_ms_max") != 250
        or controls.get("block_on_missing_or_nonfinite_metrics") is not True
        or controls.get("never_auto_tune_threshold") is not True
    ):
        raise ValueError("conveyor development screens changed")
    external = plan["external_confirmation"]
    if (
        external.get("enabled") is not False
        or external.get("approved") is not False
        or external.get("must_not_read_existing_v014_heldout") is not True
    ):
        raise ValueError("external confirmation must remain blocked")

    path = ROOT / src["corpus"]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CORPUS_SHA:
        raise ValueError("72-case development corpus SHA256 drift")
    corpus = json.loads(raw)
    if (
        corpus.get("surface") !=
        "prospective_operation_intent_development_only"
        or corpus.get("independent_holdout") is not False
        or corpus.get("execution_safety") is not False
    ):
        raise ValueError("corpus falsely claims independent safety evidence")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or len(cases) != 72:
        raise ValueError("unexpected development cohort size")
    seen: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid case")
        case_id, lang, kind = (
            case.get("id"), case.get("language"), case.get("kind")
        )
        if not isinstance(case_id, str) or case_id in seen:
            raise ValueError("duplicate/missing case ID")
        seen.add(case_id)
        if lang not in src["languages"] or kind not in ("supported", "unsupported"):
            raise ValueError("invalid language/cohort")
        expect = case.get("expected_operation")
        if (kind == "supported" and expect not in KINDS) or (
            kind == "unsupported" and expect is not None
        ):
            raise ValueError("malformed corpus ground truth")
        counts[(lang, kind)] = counts.get((lang, kind), 0) + 1
    for lang in src["languages"]:
        if counts.get((lang, "supported")) != 18:
            raise ValueError("missing language positives")
        if counts.get((lang, "unsupported")) != 6:
            raise ValueError("missing language negatives")
    return plan, corpus, digest


def _metric_rows(
    report: dict[str, Any],
    corpus: dict[str, Any],
    digest: str,
    *,
    arm: str,
) -> dict[str, float | int]:
    if report.get("corpus_sha256") != digest:
        raise ValueError(f"{arm}: source provenance mismatch")
    if report.get("independent_validation") is not False:
        raise ValueError(f"{arm}: unjustified independent qualification")
    if report.get("grants_execution_authority") is not False:
        raise ValueError(f"{arm}: forbidden execution authority")
    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != 72:
        raise ValueError(f"{arm}: incomplete report rows")
    originals = {case["id"]: case for case in corpus["cases"]}
    observed: set[str] = set()
    positives = []
    negatives = []
    latencies = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{arm}: malformed measurement")
        case_id = row.get("case_id")
        if case_id not in originals or case_id in observed:
            raise ValueError(f"{arm}: duplicate/unknown result case")
        observed.add(case_id)
        source = originals[case_id]
        if any(row.get(field) != source.get(original_field)
               for field, original_field in (
                   ("language", "language"), ("kind", "kind"),
                   ("expected_operation", "expected_operation"),
               )):
            raise ValueError(f"{arm}: tampered original case metadata")
        prediction = row.get("predicted_operation")
        if prediction is not None and prediction not in KINDS:
            raise ValueError(f"{arm}: unsupported predicted operation")
        latency = row.get("latency_ms")
        if (
            type(latency) not in (float, int)
            or not math.isfinite(latency)
            or latency < 0
        ):
            raise ValueError(f"{arm}: invalid latency")
        latencies.append(float(latency))
        if source["kind"] == "supported":
            positives.append((prediction, source["expected_operation"]))
        else:
            negatives.append(prediction)
    if len(positives) != 54 or len(negatives) != 18:
        raise ValueError(f"{arm}: cohort mismatch")
    return {
        "supported": len(positives),
        "unsupported": len(negatives),
        "supported_correct": sum(a == b for a, b in positives),
        "supported_wrong": sum(a is not None and a != b for a, b in positives),
        "supported_refused": sum(a is None for a, _ in positives),
        "unsupported_false_accepted": sum(a is not None for a in negatives),
        "latency_p95_ms": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1],
    }


def aggregate(
    baseline: dict[str, Any],
    nli: dict[str, Any],
    plan: dict[str, Any],
    corpus: dict[str, Any],
    digest: str,
) -> dict[str, Any]:
    if baseline.get("model_key") != "lexical_baseline":
        raise ValueError("unrecognized baseline model")
    if (
        nli.get("model_key") != "multilingual_nli"
        or nli.get("model_id") != plan["candidates"][1]["model"]
        or nli.get("model_revision") != NLI_REVISION
        or nli.get("threshold_calibrated") is not False
        or nli.get("no_tool_execution") is not True
    ):
        raise ValueError("unrecognized/unpinned NLI model report")
    outputs = {"lexical_baseline": baseline}
    if set(nli.get("arms", {})) != {"nli_forced", "nli_diagnostic_gate"}:
        raise ValueError("NLI study requires both preregistered arms")
    outputs.update(nli["arms"])
    metrics = {
        arm: _metric_rows(report, corpus, digest, arm=arm)
        for arm, report in outputs.items()
    }
    gates = plan["decision"]
    screened = {}
    for arm, metric in metrics.items():
        screened[arm] = {
            "passes_development_screen_only": (
                metric["supported_correct"] / 54 >= gates["supported_correct_min"]
                and metric["unsupported_false_accepted"] / 18
                <= gates["unsupported_false_accept_max"]
                and metric["supported_refused"] / 54
                <= gates["supported_false_refusal_max"]
                and metric["supported_wrong"] / 54
                <= gates["supported_wrong_operation_max"]
                and metric["latency_p95_ms"] <= gates["p95_cpu_ms_max"]
            ),
            **metric,
        }
    return {
        "state": "DEV_COMPLETE_EXTERNAL_GATE_BLOCKED",
        "corpus_sha256": digest,
        "arms": screened,
        "task_specific_classifier": "BLOCKED_NO_TRAINING_DATA_OR_MODEL",
        "independent_confirmation": "BLOCKED_UNAPPROVED_AND_NO_DISJOINT_DATA",
        "may_promote_to_product": False,
        "may_merge_release": False,
        "may_execute_tools": False,
        "frozen_v014_modified": False,
        "note": "Passing a development screen is NOT independent validation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("preflight", "aggregate"), required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--nli", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, corpus, digest = load_inputs()
    if args.stage == "preflight":
        result = {
            "state": "DEV_PREFLIGHT_READY",
            "corpus_sha256": digest,
            "source_cases": len(corpus["cases"]),
            "nli_revision": NLI_REVISION,
            "independent_confirmation": "BLOCKED",
            "training": "BLOCKED",
            "v014_conveyor_modified": False,
            "no_tool_execution": True,
        }
    else:
        if args.baseline is None or args.nli is None:
            parser.error("aggregate requires --baseline and --nli reports")
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        nli = json.loads(args.nli.read_text(encoding="utf-8"))
        result = aggregate(baseline, nli, plan, corpus, digest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reaudit frozen *development* multilingual CPU scores without running models.

The original 2026-10-15 real CPU model run is explicitly author-authored DEV
and NOT the independent 0.14 #432 corpus. This script never fits thresholds
or promotes model/agent execution and fails closed on any report alteration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SIZES = ("13", "100", "250", "500")
LANGUAGES = ("en", "ko", "ja", "es", "de", "mixed")
COUNTS = {"supported": 48, "unsupported": 36}
MODELS = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "e5-small": "intfloat/multilingual-e5-small",
}
EXPECTED_CORPUS = "dc8b0a7c9325c8767d9b323b24040e0dfe94f3fd170b829b6f977c0e629b2110"
EXPECTED_SEED = "schemarouter-multilingual-20261015-stress-v1"


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load(path: Path, digest: str) -> dict[str, Any]:
    raw = path.read_bytes()
    _check(
        type(digest) is str and len(digest) == 64
        and hashlib.sha256(raw).hexdigest() == digest,
        "model artifact bytes do not match pinned SHA-256",
    )
    return json.loads(raw)


def _audit_rows(rows: Any) -> dict[str, dict[str, Any]]:
    _check(type(rows) is list and len(rows) == 84, "missing DEV queries")
    by_id: dict[str, dict[str, Any]] = {}
    balance: dict[tuple[str, str], int] = {}
    for row in rows:
        _check(type(row) is dict, "non-object DEV result")
        case_id = row.get("case_id")
        kind, language = row.get("kind"), row.get("language")
        gold = row.get("expected_route")
        top1, top5, top10 = row.get("top_1"), row.get("top_5"), row.get("top_10")
        score = row.get("top_similarity")
        latency = row.get("latency_ms")
        _check(
            type(case_id) is str and case_id and case_id not in by_id
            and kind in COUNTS and language in LANGUAGES,
            "invalid or duplicated task identity",
        )
        _check(
            (kind == "supported" and type(gold) is str and bool(gold))
            or (kind == "unsupported" and gold is None),
            "malformed positive/negative gold route",
        )
        _check(
            type(top1) is str and bool(top1)
            and type(top5) is list and len(top5) == 5
            and type(top10) is list and len(top10) == 10
            and len(set(top10)) == 10
            and all(type(x) is str and x for x in top10)
            and top1 == top10[0] and top5 == top10[:5],
            "malformed Top-1/5/10 ranked capabilities",
        )
        _check(
            type(score) in (int, float) and math.isfinite(score)
            and -1.000001 <= score <= 1.000001
            and type(latency) in (int, float) and math.isfinite(latency)
            and latency >= 0,
            "invalid similarity or wall-time",
        )
        for k, pos in ((1, top1 == gold), (5, gold in top5), (10, gold in top10)):
            field = f"hit_at_{k}"
            _check(
                row.get(field) is (pos if kind == "supported" else None),
                "forged supported Top-K result or unsupported hit",
            )
        by_id[case_id] = row
        group = (language, kind)
        balance[group] = balance.get(group, 0) + 1
    _check(
        all(balance.get((language, "supported")) == 8
            and balance.get((language, "unsupported")) == 6
            for language in LANGUAGES),
        "language/kind DEV denominators changed",
    )
    return by_id


def audit_reports(
    reports: dict[str, dict[str, Any]],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    _check(set(reports) == set(MODELS), "expected both pinned CPU models")
    _check(
        provenance.get("source_run_id") == 38729631022
        and provenance.get("head_sha") ==
            "bc448804d7205ffb4deb4853db6225a4755bb72d"
        and provenance.get("source_repository") == "JDeun/SchemaRouter"
        and provenance.get("independent_confirmation") is False,
        "source provenance must be exact; DEV cannot claim independent proof",
    )
    by_model: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    shared: dict[str, dict[str, tuple[str, str, str | None]]] = {}
    catalog_hashes: dict[str, str] = {}
    for model, data in reports.items():
        _check(
            data.get("model_key") == model
            and data.get("model_id") == MODELS[model]
            and data.get("corpus_sha256") == EXPECTED_CORPUS
            and data.get("generator_seed") == EXPECTED_SEED
            and data.get("nested_sizes") == [13, 100, 250, 500]
            and data.get("surface") == "synthetic_stress_development_only"
            and data.get("independent_validation") is False
            and data.get("true_registered_catalog") is False
            and data.get("agent_or_execution_success") is False
            and data.get("frozen_0_14_evidence_modified") is False,
            "invalid model identity, source, corpus, or evidence scope",
        )
        result = data.get("results")
        _check(type(result) is dict and set(result) == set(SIZES),
               "missing scale cohort")
        by_model[model] = {}
        for size in SIZES:
            cell = result[size]
            _check(
                type(cell) is dict
                and type(cell.get("catalog_sha256")) is str
                and len(cell["catalog_sha256"]) == 64
                and cell.get("generated_distractors") == int(size) - 13,
                "missing source catalog identity",
            )
            catalog_hash = cell["catalog_sha256"]
            _check(
                size not in catalog_hashes
                or catalog_hashes[size] == catalog_hash,
                "different actual catalog across model comparisons",
            )
            catalog_hashes[size] = catalog_hash
            rows = _audit_rows(cell.get("rows"))
            by_model[model][size] = rows
            identity = {
                k: (r["language"], r["kind"], r["expected_route"])
                for k, r in rows.items()
            }
            if size not in shared:
                shared[size] = identity
            else:
                _check(shared[size] == identity,
                       "different labels/queries across real model runs")
            _check(
                size == "13" or set(rows) == set(by_model[model]["13"]),
                "different task identities across catalog scales",
            )
            _check(
                size == "13" or identity == shared["13"],
                "task gold identities differ from original 13-route DEV",
            )
    summary: dict[str, dict[str, Any]] = {}
    for model in MODELS:
        summary[model] = {}
        for size in SIZES:
            rows = by_model[model][size]
            supported = [r for r in rows.values() if r["kind"] == "supported"]
            unsupported = [r for r in rows.values() if r["kind"] == "unsupported"]
            min_supported = min(r["top_similarity"] for r in supported)
            max_unsupported = max(r["top_similarity"] for r in unsupported)
            initial = by_model[model]["13"]
            baseline_top1_losses = sorted(
                k for k, r in rows.items()
                if r["kind"] == "supported"
                and initial[k]["hit_at_1"] and not r["hit_at_1"]
            )
            languages = {}
            for lang in LANGUAGES:
                yes = [r for r in supported if r["language"] == lang]
                no = [r for r in unsupported if r["language"] == lang]
                languages[lang] = {
                    "supported": len(yes),
                    "unsupported": len(no),
                    "correct_top1": sum(bool(r["hit_at_1"]) for r in yes),
                    "correct_top5": sum(bool(r["hit_at_5"]) for r in yes),
                    "unsupported_top1_always_present": len(no),
                    "min_supported_score": min(r["top_similarity"] for r in yes),
                    "max_unsupported_score": max(r["top_similarity"] for r in no),
                    "perfect_scalar_threshold_possible": (
                        min(r["top_similarity"] for r in yes)
                        > max(r["top_similarity"] for r in no)
                    ),
                }
            summary[model][size] = {
                "catalog_sha256": catalog_hashes[size],
                "supported": len(supported),
                "unsupported": len(unsupported),
                "top1_correct": sum(bool(r["hit_at_1"]) for r in supported),
                "top5_correct": sum(bool(r["hit_at_5"]) for r in supported),
                "top10_correct": sum(bool(r["hit_at_10"]) for r in supported),
                "minimum_supported_similarity": min_supported,
                "maximum_unsupported_similarity": max_unsupported,
                "unsupported_above_weakest_supported": sum(
                    r["top_similarity"] >= min_supported for r in unsupported
                ),
                "perfect_scalar_threshold_possible": min_supported > max_unsupported,
                "lost_top1_since_13": baseline_top1_losses,
                "by_language": languages,
            }
    return {
        "schema_version": 1,
        "kind": "source_pinned_multilingual_score_overlap_DEV_audit",
        "provenance": provenance,
        "corpus_sha256": EXPECTED_CORPUS,
        "models": summary,
        "scope": {
            "previously_exposed_author_written_synthetic_DEV": True,
            "scalar_threshold_fitted": False,
            "threshold_promoted_to_product": False,
            "real_provider_schemas": False,
            "independent_confirmation": False,
            "host_authorization": False,
            "actual_agent_or_tool_task_success": False,
            "may_release": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minilm", type=Path, required=True)
    parser.add_argument("--e5", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw = manifest.get("reports")
    _check(type(raw) is dict and set(raw) == set(MODELS),
           "invalid pinned source report map")
    reports = {
        "minilm": _load(args.minilm, raw["minilm"]["sha256"]),
        "e5-small": _load(args.e5, raw["e5-small"]["sha256"]),
    }
    output = audit_reports(reports, provenance={
        key: manifest[key] for key in (
            "source_repository", "source_run_id", "head_sha",
            "independent_confirmation",
        )
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": output["kind"], "model_count": 2,
        "source_run": manifest["source_run_id"],
        "perfect_score_threshold_500": {
            k: output["models"][k]["500"]["perfect_scalar_threshold_possible"]
            for k in MODELS
        },
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Score model-inferred required fields from real authorized OpenAPI enums.

Unlike host-oracle studies #1443/#1445, E5 sees only query text and
published typed *authorized* enum fields. Expected requirements are loaded
AFTER prediction solely for scoring. This is same-author development,
NOT a calibrated trusted intent extractor, execution policy or release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    PlanRequest,
    choose_sync,
)
from scripts.research_open_meteo_real_openapi_dev import (
    LANGUAGES,
    QUERIES,
    SOURCE_NAMES,
    UNSUPPORTED,
)
from scripts.research_real_open_meteo_e5_cpu_dev import (
    MODEL_ID,
    MODEL_REVISION,
    catalog,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_FIELDS = 2048
MAX_ENUM_ITEMS = 1024
FIELD_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
TOP_WIDTH = 10
PASSAGE_STYLES = ("name_only", "parameter_context")


def authorized_enum_fields(
    authorized_candidates: list[Any],
) -> tuple[list[tuple[str, str]], dict[str, list[str]], dict[str, Any]]:
    """Extract from already authorized, projected candidate metadata only."""
    source_routes: dict[str, list[str]] = {}
    seen: dict[tuple[str, str], set[str]] = {}
    stats: dict[str, Any] = {
        "ignored_non_enum_or_invalid_parameter": 0,
        "ignored_non_string_values": 0,
        "seen_route_count": 0,
    }
    ids: set[str] = set()
    for c in authorized_candidates:
        rid = c.route_id
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError("duplicated or invalid authorized route id")
        ids.add(rid)
        stats["seen_route_count"] += 1
        if c.read_only is not True:
            continue
        for item in c.parameters:
            if item.location != "query" or not isinstance(item.name, str):
                stats["ignored_non_enum_or_invalid_parameter"] += 1
                continue
            name = item.name
            if not FIELD_ID.fullmatch(name):
                stats["ignored_non_enum_or_invalid_parameter"] += 1
                continue
            schema = item.json_schema
            if not isinstance(schema, dict):
                stats["ignored_non_enum_or_invalid_parameter"] += 1
                continue
            enum = schema.get("enum")
            if schema.get("type") == "array":
                items = schema.get("items")
                enum = items.get("enum") if isinstance(items, dict) else None
            if not isinstance(enum, list) or len(enum) > MAX_ENUM_ITEMS:
                stats["ignored_non_enum_or_invalid_parameter"] += 1
                continue
            for value in enum:
                if type(value) is not str or not FIELD_ID.fullmatch(value):
                    stats["ignored_non_string_values"] += 1
                    continue
                key = (name, value)
                seen.setdefault(key, set()).add(rid)
                if len(seen) > MAX_FIELDS:
                    raise ValueError("bounded actual field inventory exceeded")
    fields = sorted(seen)
    if not fields:
        raise ValueError("no authorized published enum variable candidates")
    for (param, value), routes in seen.items():
        source_routes[f"{param}:{value}"] = sorted(routes)
    stats["distinct_enum_fields"] = len(fields)
    return fields, source_routes, stats


def field_options(
    fields: list[tuple[str, str]],
    style: str,
) -> list[DecisionOption]:
    if style not in PASSAGE_STYLES:
        raise ValueError("unregistered field passage style")
    options = []
    for param, value in fields:
        field_words = value.replace("_", " ").replace("-", " ")
        param_words = param.replace("_", " ")
        description = (
            field_words if style == "name_only"
            else f"Weather observation or forecast variable: {field_words}. "
                 f"Published API parameter: {param_words}. "
                 f"Official schema enum value: {value}."
        )
        options.append(DecisionOption(
            id=f"field:{param}:{value}",
            label=f"{param}.{value}",
            description=description,
        ))
    return options


def infer_field_rankings(
    query: str,
    approved_fields: list[tuple[str, str]],
    backends: dict[str, EmbeddingDecisionBackend],
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, float]]:
    """No gold, expected source or human-oracle field may enter this call."""
    if not query or not query.strip():
        raise ValueError("empty user query")
    ranked: dict[str, list[tuple[str, str]]] = {}
    time_ms = {}
    for style in PASSAGE_STYLES:
        options = field_options(approved_fields, style)
        started = time.perf_counter_ns()
        outcome = choose_sync(backends[style], DecisionRequest(
            query=query,
            options=options,
            max_selections=min(TOP_WIDTH, len(options)),
        ))
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if (
            outcome.abstained or not math.isfinite(elapsed) or elapsed < 0
            or len(outcome.selections) != min(TOP_WIDTH, len(options))
        ):
            raise ValueError("missing or invalid real CPU field prediction")
        mapped = {
            f"field:{param}:{value}": (param, value)
            for param, value in approved_fields
        }
        ids = [selection.option_id for selection in outcome.selections]
        if len(ids) != len(set(ids)) or not set(ids).issubset(mapped):
            raise ValueError("E5 returned unknown, duplicate or denied enum")
        ranked[style] = [mapped[opt_id] for opt_id in ids]
        time_ms[style] = round(elapsed, 5)
    return ranked, time_ms


def evaluate(
    manifest: Path,
    source_dir: Path,
    encoder: Any,
    *,
    model_revision: str,
) -> dict[str, Any]:
    if model_revision != MODEL_REVISION:
        raise ValueError("immutable source model revision required")
    router, principal, allowed_source_routes, evidence = catalog(
        manifest, source_dir,
    )
    approved_routes = {
        rid for routes in allowed_source_routes.values() for rid in routes
    }
    if len(approved_routes) != 9:
        raise ValueError("current published nine-route study must remain fixed")
    backends = {
        style: EmbeddingDecisionBackend(
            E5CachedEmbedder(encoder, max_cached_passages=MAX_FIELDS),
        )
        for style in PASSAGE_STYLES
    }
    cases: list[dict[str, Any]] = []
    expected_field_space: list[tuple[str, str]] | None = None
    field_routes: dict[str, list[str]] = {}
    inventory_stats: dict[str, Any] = {}
    tasks = [
        (src, lang, query, True)
        for src in SOURCE_NAMES
        for lang, query in zip(LANGUAGES, QUERIES[src], strict=True)
    ] + [
        (kind, lang, query, False)
        for kind, *queries in UNSUPPORTED
        for lang, query in zip(LANGUAGES, queries, strict=True)
    ]
    if len(tasks) != 36:
        raise ValueError("changed English/Korean/Japanese evaluation cohort")
    # No gold-route or manually supplied variable in these loops.
    for source, lang, query, supported in tasks:
        approved = router.retrieve_authorized(
            PlanRequest(query=query), principal=principal, k=9,
        ).candidates
        ids = [c.route_id for c in approved]
        if len(ids) != 9 or set(ids) != approved_routes:
            raise ValueError("unauthorized or omitted current API route")
        fields, owners, stats = authorized_enum_fields(approved)
        if expected_field_space is None:
            expected_field_space = fields
            field_routes = owners
            inventory_stats = stats
        elif fields != expected_field_space or owners != field_routes:
            raise ValueError("query changed authorized enum inventory")
        predictions, durations = infer_field_rankings(
            query, fields, backends,
        )
        cases.append({
            "source": source,
            "language": lang,
            "kind": "supported" if supported else "unsupported",
            "predicted": {
                style: [list(p) for p in predicted]
                for style, predicted in predictions.items()
            },
            "latency_ms": durations,
            "all_predicted_from_authorized_source": True,
            "no_reject_threshold_or_execution": True,
        })
    if expected_field_space is None:
        raise ValueError("no real current source approved")
    # Gold is loaded only AFTER the E5 predictions are fixed in 'cases'.
    from scripts.research_openapi_conjunctive_enum_dev import DEV_REQUIRED_PAIRS

    for record in cases:
        if record["kind"] != "supported":
            record["human_gold_fields_for_scoring_only"] = None
            record["field_hit_at_1"] = None
            record["field_hit_at_5"] = None
            record["all_required_hit_at_10"] = None
            continue
        gold = DEV_REQUIRED_PAIRS[record["source"]]
        record["human_gold_fields_for_scoring_only"] = [list(p) for p in gold]
        record["field_hit_at_1"] = {
            style: bool(gold) and tuple(record["predicted"][style][0]) in gold
            for style in PASSAGE_STYLES
        }
        record["field_hit_at_5"] = {
            style: bool(gold) and any(
                tuple(p) in gold for p in record["predicted"][style][:5]
            )
            for style in PASSAGE_STYLES
        }
        record["all_required_hit_at_10"] = {
            style: bool(gold) and all(
                list(g) in record["predicted"][style] for g in gold
            )
            for style in PASSAGE_STYLES
        }
    language_summary = {}
    for language in (*LANGUAGES, "all"):
        positives = [
            c for c in cases if c["kind"] == "supported" and
            (language == "all" or language == c["language"])
        ]
        negatives = [
            c for c in cases if c["kind"] == "unsupported" and
            (language == "all" or language == c["language"])
        ]
        known = [
            x for x in positives if x["human_gold_fields_for_scoring_only"]
        ]
        if len(positives) != (27 if language == "all" else 9):
            raise ValueError("invalid supported denominator")
        if len(negatives) != (9 if language == "all" else 3):
            raise ValueError("invalid unsupported denominator")
        language_summary[language] = {
            "supported": len(positives),
            "gold_defined": len(known),
            "unsupported_unscored": len(negatives),
            "top1_contains_any_required_field": {
                style: sum(x["field_hit_at_1"][style] for x in known)
                for style in PASSAGE_STYLES
            },
            "top5_contains_any_required_field": {
                style: sum(x["field_hit_at_5"][style] for x in known)
                for style in PASSAGE_STYLES
            },
            "top10_contains_all_required_fields": {
                style: sum(x["all_required_hit_at_10"][style] for x in known)
                for style in PASSAGE_STYLES
            },
        }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "study": "publisher_authorized_multilingual_query_to_enum_fields_dev",
        "schema_commit": commit,
        "publisher_original_blob_sha256": {
            n: evidence[n]["sha256"] for n in SOURCE_NAMES
        },
        "provider_manifest_sha256": hashlib.sha256(
            manifest.read_bytes()
        ).hexdigest(),
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "distinct_authorized_field_pairs": len(expected_field_space),
        "inventory": inventory_stats,
        "fields_to_approved_route_ids": field_routes,
        "cases": cases,
        "by_language": language_summary,
        "cpu_peak_resident_kib": resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "runner_id": os.getenv("GITHUB_RUN_ID"),
        "scope": {
            "published_provider_schemas": True,
            "real_local_multilingual_model": True,
            "field_inference_uses_human_gold": False,
            "gold_loaded_only_for_posthoc_scoring": True,
            "developer_authored_queries_and_gold": True,
            "unseen_or_independent_test": False,
            "field_predictions_not_authenticated_user_requirements": True,
            "real_host_authorization_or_no_fit_verification": False,
            "actual_tool_or_agent_execution": False,
            "may_change_default_or_release": False,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--source-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(os.cpu_count() or 1, 4))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION,
        trust_remote_code=False, device="cpu",
    )
    if model.device.type != "cpu":
        raise ValueError("must execute E5 locally on CPU")
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(
            texts, batch_size=16,
            convert_to_numpy=True, normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
        if any(not math.isfinite(v) for row in vectors for v in row):
            raise ValueError("invalid real embedding vector")
        return vectors

    report = evaluate(
        args.manifest, args.source_dir, encode,
        model_revision=MODEL_REVISION,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["study"],
        "fields": report["distinct_authorized_field_pairs"],
        "languages": report["by_language"],
        "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pinned native Xerrion ServiceNow DEV: current lexical vs local E5 rerank.

Uses ONLY source-visible, already published developer-authored tasks. No agent,
API requests, authorization grant, live ServiceNow execution, or no-fit claim.
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
from pathlib import Path
from typing import Any

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    SchemaRouter,
    choose_sync,
)
from schemarouter.adapters.mcp import tool_from_mcp
from scripts.external_validation_servicenow_platform_mcp import (
    load_package,
    validate_package,
)
from scripts.research_real_open_meteo_e5_cpu_dev import MODEL_ID, MODEL_REVISION

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (3, 5)
EXPECTED_TOOL_COUNT = 12
EXPECTED_SUPPORTED = 20
EXPECTED_UNSUPPORTED = 4


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def strict_permutation(ranked: list[str], allowed: set[str]) -> None:
    """A model may only reorder the exact original native readonly catalog."""
    if (
        type(ranked) is not list
        or len(ranked) != len(allowed)
        or any(type(name) is not str for name in ranked)
        or len(set(ranked)) != len(ranked)
        or set(ranked) != allowed
    ):
        raise ValueError("E5 did not return an exact native-source permutation")


def case_metrics(
    case: dict[str, Any],
    selected: list[str],
    source_tools: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if len(set(selected)) != len(selected) or set(selected) - set(source_tools):
        raise ValueError("selected tool identity is not native")
    expected = set(case["required_tools"])
    covered = expected & set(selected)
    field_total = 0
    field_hits = 0
    for name, fields in case["required_fields"].items():
        field_total += len(fields)
        if name in selected:
            params = source_tools[name]["inputSchema"]["properties"]
            field_hits += len(set(fields) & set(params))
    if case["label"] == "supported" and not expected:
        raise ValueError("supported case without required tools")
    if case["label"] == "unsupported" and (expected or field_total):
        raise ValueError("unsupported case has forbidden gold")
    return {
        "route_hits": len(covered),
        "route_required": len(expected),
        "field_hits": field_hits,
        "field_required": field_total,
        "visible_native_bytes": len(canonical([source_tools[n] for n in selected])),
        "unsupported_nonempty_not_no_fit": (
            bool(selected) if case["label"] == "unsupported" else None
        ),
    }


def summarize(
    rows: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    cases_by_id = {c["id"]: c for c in cases}
    if len(rows) != len(cases_by_id):
        raise ValueError("missing or duplicate study rows")
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("duplicate measured case identity")
    out: dict[str, Any] = {}
    for arm in ("static_full", "lexical_k3", "lexical_k5", "e5_k3", "e5_k5"):
        scores = [r["metrics"][arm] for r in rows]
        supported = [
            s for s, r in zip(scores, rows, strict=True)
            if cases_by_id[r["id"]]["label"] == "supported"
        ]
        negatives = [
            s for s, r in zip(scores, rows, strict=True)
            if cases_by_id[r["id"]]["label"] == "unsupported"
        ]
        route_total = sum(s["route_required"] for s in supported)
        field_total = sum(s["field_required"] for s in supported)
        if not route_total or not field_total or len(negatives) != EXPECTED_UNSUPPORTED:
            raise ValueError("incomplete native DEV metric denominators")
        out[arm] = {
            "supported_cases": len(supported),
            "required_tool_recall_macro": sum(
                s["route_hits"] / s["route_required"] for s in supported
            ) / len(supported),
            "required_tool_recall_micro": sum(
                s["route_hits"] for s in supported
            ) / route_total,
            "native_input_field_recall_micro": sum(
                s["field_hits"] for s in supported
            ) / field_total,
            "mean_exposed_native_contract_bytes": sum(
                s["visible_native_bytes"] for s in scores
            ) / len(scores),
            "unsupported_nonempty_exposure_count_not_no_fit": sum(
                s["unsupported_nonempty_not_no_fit"] for s in negatives
            ),
        }
    return out


def evaluate(
    package_dir: Path,
    snapshot_path: Path,
    encoder: Any,
    *,
    model_revision: str = MODEL_REVISION,
) -> dict[str, Any]:
    if model_revision != MODEL_REVISION:
        raise ValueError("unpinned or changed local E5 model revision")
    manifest, cases, snapshot = load_package(package_dir, snapshot_path)
    validate_package(manifest, cases, snapshot)
    if (
        len(snapshot["tools"]) != EXPECTED_TOOL_COUNT
        or manifest["counts"] != {
            "cases": 24, "supported": EXPECTED_SUPPORTED,
            "unsupported": EXPECTED_UNSUPPORTED,
        }
        or sorted(manifest["comparison"]["development_top_k_sensitivity"])
        != list(WIDTHS)
    ):
        raise ValueError("native package or original DEV arms drifted")

    tool_map = {tool["name"]: tool for tool in snapshot["tools"]}
    allowed = set(tool_map)
    router = SchemaRouter()
    router.add_tool(tool_from_mcp(
        "servicenow-platform-mcp", {"tools": snapshot["tools"]},
        namespace="external-validation-servicenow-platform-mcp",
    ))
    backend = EmbeddingDecisionBackend(E5CachedEmbedder(
        encoder, max_cached_passages=256,
    ))
    rows = []
    for case in cases["cases"]:
        # Full same-source retrieval first. Reranker has no access to gold.
        start = time.perf_counter_ns()
        full = router.retrieve(case["query"], k=EXPECTED_TOOL_COUNT)
        retrieval_ms = (time.perf_counter_ns() - start) / 1e6
        lexical = [c.endpoint for c in full.candidates]
        strict_permutation(lexical, allowed)
        options = [
            DecisionOption(
                id=c.endpoint, label=c.endpoint,
                description="\n".join([
                    c.tool_description, c.endpoint_description,
                ]),
            )
            for c in full.candidates
        ]
        start = time.perf_counter_ns()
        decision = choose_sync(backend, DecisionRequest(
            query=case["query"], options=options,
            max_selections=EXPECTED_TOOL_COUNT,
        ))
        e5_ms = (time.perf_counter_ns() - start) / 1e6
        ranked = [selection.option_id for selection in decision.selections]
        strict_permutation(ranked, allowed)
        if decision.abstained or not all(
            math.isfinite(v) and v >= 0 for v in (retrieval_ms, e5_ms)
        ):
            raise ValueError("invalid unthresholded E5 or lexical DEV sample")
        arms = {
            "static_full": list(tool_map),
            "lexical_k3": lexical[:3],
            "lexical_k5": lexical[:5],
            "e5_k3": ranked[:3],
            "e5_k5": ranked[:5],
        }
        rows.append({
            "id": case["id"], "kind": case["label"],
            "original_visible_dev_query": case["query"],
            "lexical_order": lexical, "e5_order": ranked,
            "local_full_retrieval_ms": retrieval_ms,
            "local_e5_rerank_ms": e5_ms,
            "selected": arms,
            "metrics": {
                arm: case_metrics(case, names, tool_map)
                for arm, names in arms.items()
            },
        })
    if len(rows) != EXPECTED_SUPPORTED + EXPECTED_UNSUPPORTED:
        raise ValueError("original author-DEV cases missing")
    summary = summarize(rows, cases["cases"])
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT, check=True, text=True, capture_output=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "study": "native_servicenow_original_visible_dev_e5_vs_lexical",
        "status": "same_author_visible_dev_not_independent",
        "implementation_revision": revision,
        "upstream_repository": snapshot["source"]["repository"],
        "upstream_commit": snapshot["source"]["commit"],
        "native_readonly_tools_sha256": snapshot["tools_sha256"],
        "manifest_sha256": hashlib.sha256(
            (package_dir / "manifest.json").read_bytes()
        ).hexdigest(),
        "cases_sha256": hashlib.sha256(
            (package_dir / manifest["files"]["cases"]).read_bytes()
        ).hexdigest(),
        "model_id": MODEL_ID, "model_revision": model_revision,
        "summary": summary, "cases": rows,
        "local_cpu_platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "actions_run_id": os.getenv("GITHUB_RUN_ID"),
        "limitations": {
            "original_visible_dev_only": True,
            "case_language": "english_original_only",
            "independent_e2": False,
            "model_reranks_authorized_native_routes_only": True,
            "no_fit_calibrated": False,
            "no_service_now_tenant_credentials_or_calls": True,
            "native_tool_execution": False,
            "agent_task_success_measured": False,
            "commercial_latency_sla": False,
            "product_default_changed": False,
            "release_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION,
        trust_remote_code=False, device="cpu",
    )
    if model.device.type != "cpu":
        raise ValueError("real model must run on CPU")
    model.eval()

    def encode(texts: list[str]) -> list[list[float]]:
        values = model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()
        if any(not math.isfinite(v) for row in values for v in row):
            raise ValueError("invalid embedding")
        return values

    result = evaluate(
        args.package_dir, args.snapshot, encode,
        model_revision=MODEL_REVISION,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": result["study"], "summary": result["summary"],
        "independent": False, "release_authorized": False,
    }, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

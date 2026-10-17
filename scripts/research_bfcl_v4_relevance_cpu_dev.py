"""Publisher-pinned BFCL V4 operation relevance, no execution, DEV comparison.

Measures real SchemaRouter lexical retrieval vs opt-in pinned real CPU E5,
each on the same *per-case publisher-defined* tool catalog.  Calibrated
thresholds use a disjoint-by-ID slice of a PUBLIC benchmark, so no E2 claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any

from schemarouter import EndpointSpec, InMemoryRegistry, SchemaRouter, ToolSpec
from schemarouter.decisions import (
    DecisionOption, DecisionRequest, EmbeddingDecisionBackend, choose_sync,
)
from schemarouter.embedding_e5 import E5CachedEmbedder

UPSTREAM_REPO = "ShishirPatil/gorilla"
UPSTREAM_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
ORIGINAL_BLOBS = {
    "multiple": ("BFCL_v4_multiple.json", "83643fa853e7a29a50e7303b0279284c37dd63c8", 200),
    "irrelevance": ("BFCL_v4_irrelevance.json", "0077629949f2d52734cef2f110b0d040d8c47554", 240),
    "gold": ("BFCL_v4_multiple_ground_truth.json", "1f2f1fbfd9b7c8859ef5a92d6c18b0a6b2bc2663", 200),
}
CALIBRATION_FRACTION = "even IDs (100 supported + 120 unsupported)"
EVALUATION_FRACTION = "odd IDs (100 supported + 120 unsupported)"
MAX_FALSE_ACCEPT_CALIBRATION = 0.10


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
    ).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate source JSON key")
        result[key] = value
    return result


def _no_nonfinite(value: str) -> None:
    raise ValueError("nonfinite publisher JSON not allowed")


def load_jsonl(path: Path, *, original_blob: str, count: int) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if git_blob_sha1(raw) != original_blob:
        raise ValueError("BFCL publisher source blob drift")
    lines = raw.splitlines()
    if len(lines) != count:
        raise ValueError("BFCL publisher case count drift")
    result: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for line in lines:
        row = json.loads(
            line.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
            parse_constant=_no_nonfinite,
        )
        if type(row) is not dict or type(row.get("id")) is not str:
            raise ValueError("invalid BFCL record")
        if row["id"] in identifiers:
            raise ValueError("duplicate publisher case ID")
        identifiers.add(row["id"])
        result.append(row)
    return result


def load_originals(directory: Path) -> list[dict[str, Any]]:
    original = {
        kind: load_jsonl(
            directory / filename, original_blob=sha1, count=count,
        ) for kind, (filename, sha1, count) in ORIGINAL_BLOBS.items()
    }
    gold = {record["id"]: record for record in original["gold"]}
    if set(gold) != {r["id"] for r in original["multiple"]}:
        raise ValueError("publisher question/gold ID mismatch")
    results: list[dict[str, Any]] = []
    for kind in ("multiple", "irrelevance"):
        for row in original[kind]:
            ident = row["id"]
            if not ident.startswith(kind + "_"):
                raise ValueError("unexpected publisher case kind")
            idx = ident[len(kind) + 1:]
            if not idx.isdigit():
                raise ValueError("unexpected publisher case ordinal")
            turns = row.get("question")
            if (
                type(turns) is not list or len(turns) != 1
                or type(turns[0]) is not list or len(turns[0]) != 1
                or turns[0][0].get("role") != "user"
                or type(turns[0][0].get("content")) is not str
                or not turns[0][0]["content"].strip()
            ):
                raise ValueError("unsupported publisher multi-turn shape")
            functions = row.get("function")
            if type(functions) is not list or not 1 <= len(functions) <= 32:
                raise ValueError("unexpected BFCL offered function count")
            names = [f.get("name") for f in functions if type(f) is dict]
            if (
                len(names) != len(functions)
                or any(type(name) is not str or not name for name in names)
                or len(set(names)) != len(names)
            ):
                raise ValueError("invalid publisher function inventory")
            expected: str | None = None
            if kind == "multiple":
                truth = gold[ident].get("ground_truth")
                if (
                    type(truth) is not list or len(truth) != 1
                    or type(truth[0]) is not dict or len(truth[0]) != 1
                ):
                    raise ValueError("unsupported multi-call gold label")
                expected = next(iter(truth[0]))
                if expected not in names:
                    raise ValueError("gold operation absent from offered functions")
            results.append({
                "id": ident, "kind": kind, "split": "calibration" if int(idx) % 2 == 0
                else "evaluation", "query": turns[0][0]["content"],
                "functions": functions, "expected": expected,
            })
    strata = {
        (kind, split): sum(
            row["kind"] == kind and row["split"] == split for row in results
        ) for kind in ("multiple", "irrelevance")
        for split in ("calibration", "evaluation")
    }
    if strata != {
        ("multiple", "calibration"): 100,
        ("multiple", "evaluation"): 100,
        ("irrelevance", "calibration"): 120,
        ("irrelevance", "evaluation"): 120,
    }:
        raise ValueError("missing BFCL held-split denominators")
    return results


def option_text(function: dict[str, Any]) -> str:
    """Function-origin words only; no publisher gold, output or source ID."""
    name = function["name"]
    description = function.get("description", "")
    params = function.get("parameters", {})
    properties = params.get("properties", {}) if type(params) is dict else {}
    if (
        type(description) is not str or type(properties) is not dict
        or any(type(k) is not str or type(v) is not dict for k, v in properties.items())
    ):
        raise ValueError("invalid BFCL source parameters")
    details = []
    for key, info in properties.items():
        value = info.get("description", "")
        if type(value) is not str:
            raise ValueError("invalid BFCL parameter description")
        details.append(key.replace("_", " ") + ": " + value)
    return "\n".join([name.replace("_", " "), description, *details])


def default_lexical_one(row: dict[str, Any]) -> tuple[str, float]:
    registry = InMemoryRegistry()
    labels = []
    for idx, function in enumerate(row["functions"]):
        label = function["name"]
        labels.append(label)
        registry.register(ToolSpec(
            name=f"bfcl_{idx}", description=option_text(function),
            endpoints=[EndpointSpec(name="call", read_only=True)],
        ))
    router = SchemaRouter(registry=registry)
    result = router.retrieve(row["query"], k=1)
    if len(result.candidates) != 1:
        raise ValueError("real lexical retrieval omitted source candidate")
    matched = result.candidates[0]
    idx = int(matched.route_id.split(".")[0].removeprefix("bfcl_"))
    if not 0 <= idx < len(labels):
        raise ValueError("out-of-source lexical route")
    return labels[idx], float(matched.score)


def embedding_one(row: dict[str, Any], backend: EmbeddingDecisionBackend) -> tuple[str, float]:
    offered = row["functions"]
    result = choose_sync(backend, DecisionRequest(
        query=row["query"],
        options=[
            DecisionOption(
                id=f"bfcl_{idx}", label=fn["name"],
                description=option_text(fn),
            ) for idx, fn in enumerate(offered)
        ],
        max_selections=1,
    ))
    if result.abstained or len(result.selections) != 1:
        raise ValueError("unthresholded real model failed to choose one offered route")
    selection = result.selections[0]
    idx = int(selection.option_id.removeprefix("bfcl_"))
    if not 0 <= idx < len(offered):
        raise ValueError("untrusted semantic result escaped offered source IDs")
    score = result.metadata["top_similarity"]
    if type(score) is not float or not math.isfinite(score):
        raise ValueError("nonfinite semantic similarity")
    return offered[idx]["name"], score


def calibrate_threshold(rows: list[dict[str, Any]], score_key: str) -> float:
    """Choose only a published-DEV operating point, never an independent gate.

    Strictly above the 13th highest negative score gives <=12/120 false
    acceptance on calibration (ties may lower it further).
    """
    negatives = sorted(
        (row[score_key] for row in rows
         if row["split"] == "calibration" and row["kind"] == "irrelevance"),
        reverse=True,
    )
    if len(negatives) != 120 or any(not math.isfinite(v) for v in negatives):
        raise ValueError("missing finite calibration negatives")
    return math.nextafter(negatives[12], math.inf)


def metrics(rows: list[dict[str, Any]], score_key: str, route_key: str,
            threshold: float, *, split: str) -> dict[str, Any]:
    s = [r for r in rows if r["split"] == split and r["kind"] == "multiple"]
    n = [r for r in rows if r["split"] == split and r["kind"] == "irrelevance"]
    if len(s) != 100 or len(n) != 120:
        raise ValueError("invalid published cohort denominator")
    return {
        "supported": len(s), "unsupported": len(n),
        "forced_supported_correct": sum(r[route_key] == r["expected"] for r in s),
        "supported_correct_after_gate": sum(
            r[route_key] == r["expected"] and r[score_key] >= threshold for r in s
        ),
        "supported_false_refusal": sum(r[score_key] < threshold for r in s),
        "supported_wrong_accepted": sum(
            r[score_key] >= threshold and r[route_key] != r["expected"] for r in s
        ),
        "unsupported_false_accept": sum(r[score_key] >= threshold for r in n),
        "unsupported_correct_refusal": sum(r[score_key] < threshold for r in n),
    }


def evaluate(rows: list[dict[str, Any]], encoder: Any) -> dict[str, Any]:
    backend = EmbeddingDecisionBackend(
        E5CachedEmbedder(encoder, max_cached_passages=2048),
    )
    completed: list[dict[str, Any]] = []
    times: list[float] = []
    for row in rows:
        lexical_route, lexical_score = default_lexical_one(row)
        start = time.perf_counter()
        e5_route, e5_score = embedding_one(row, backend)
        times.append(time.perf_counter() - start)
        completed.append({
            "id": row["id"], "kind": row["kind"], "split": row["split"],
            "expected": row["expected"], "lexical_route": lexical_route,
            "lexical_score": lexical_score,
            "e5_route": e5_route, "e5_score": e5_score,
        })
    arms = {}
    for arm in ("lexical", "e5"):
        score_key, route_key = arm + "_score", arm + "_route"
        threshold = calibrate_threshold(completed, score_key)
        arms[arm] = {
            "calibrated_threshold_on_public_cases": threshold,
            "calibration": metrics(
                completed, score_key, route_key, threshold, split="calibration",
            ),
            "evaluation": metrics(
                completed, score_key, route_key, threshold, split="evaluation",
            ),
        }
    return {
        "study": "BFCL_V4_PUBLIC_PAIRED_OPERATION_RELEVANCE_DEV_ONLY",
        "original_provider": UPSTREAM_REPO, "source_commit": UPSTREAM_COMMIT,
        "source_blob_sha1": {k: v[1] for k, v in ORIGINAL_BLOBS.items()},
        "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
        "case_count": len(completed),
        "split": {"calibration": CALIBRATION_FRACTION,
                  "evaluation": EVALUATION_FRACTION},
        "target_calibration_false_accept_rate": MAX_FALSE_ACCEPT_CALIBRATION,
        "by_arm": arms,
        "real_model_wall_seconds_total": round(sum(times), 3),
        "real_model_inference_measured": True,
        "native_provider_tools_executed": False,
        "query_language": "en_only",
        "independent_e2_qualified": False,
        "external_author_disjoint_private_confirmation": False,
        "model_default_changed": False,
        "release_safety_gate_passed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = load_originals(args.source_dir)
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION,
        trust_remote_code=False, device="cpu",
    )
    model.eval()
    if model.device.type != "cpu":
        raise RuntimeError("CPU-only BFCL model study required")

    def encode(texts: list[str]) -> list[list[float]]:
        return model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        ).tolist()

    report = evaluate(rows, encode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"case_count": report["case_count"], "arms": report["by_arm"],
                      "e2": report["independent_e2_qualified"]}))


if __name__ == "__main__":
    main()

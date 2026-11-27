"""Public-fixture real small-model Understand pilot, not original answer replication.

Only the public inventory and raw query reach the restored planner. Archived
selected calls are a historical agreement reference, not gold. No private paper
repository, answer keys, provider data, or remote inference API is accessed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from statistics import mean
from typing import Any

from schemarouter import PrincipalContext
from scripts.research_original_paper_inventory import build_original_paper_inventory
from scripts.research_original_paper_model_replay import (
    ROOT,
    MeasuredModel,
    _cohort,
    _current_plan,
    _git,
    _local_backend,
)

FIXTURE = ROOT / "tests/fixtures/original_paper_full_replay.json"
FIXTURE_BLOB = "fbfe0dcf5b2bfcff325bf673d5bcd3bab5b3985e"
PILOT_SIZE = 9


def _load_fixture() -> dict[str, Any]:
    data = FIXTURE.read_bytes()
    blob = hashlib.sha1(
        f"blob {len(data)}\0".encode() + data, usedforsecurity=False,
    ).hexdigest()
    if blob != FIXTURE_BLOB:
        raise ValueError("public original replay fixture changed")
    fixture = json.loads(data)
    if len(fixture["inventory"]["apis"]) != 19:
        raise ValueError("original public source inventory changed")
    return fixture


def _agreement(actual: list[dict], archived: list[dict]) -> dict[str, float]:
    actual_tools = {call["tool"] for call in actual}
    archived_tools = {call["tool"] for call in archived}
    actual_fields = {(call["tool"], name) for call in actual for name in call["fields"]}
    archived_fields = {(call["tool"], name) for call in archived for name in call["fields"]}
    overlap = len(actual_fields & archived_fields)
    if not actual_fields and not archived_fields:
        precision = recall = 1.0
    else:
        precision = overlap / len(actual_fields) if actual_fields else 0.0
        recall = overlap / len(archived_fields) if archived_fields else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "archived_tool_set_exact": float(actual_tools == archived_tools),
        "archived_field_set_exact": float(actual_fields == archived_fields),
        "archived_field_precision": precision,
        "archived_field_recall": recall,
        "archived_field_f1": f1,
    }


async def _case(session, intents, rank, actor, measured, case) -> dict[str, Any]:
    measured.calls.clear()
    measured.stage = "understand"
    raw = {"query_id": case["query_id"], "query": case["query"]}
    started = time.monotonic()
    plan, diagnostic = await _current_plan(session, intents, rank, actor, measured, raw)
    elapsed = time.monotonic() - started
    if len(measured.calls) != 1 or measured.calls[0]["stage"] != "understand":
        raise ValueError("missing or unexpected Understand call receipt")
    call = dict(measured.calls[0])
    if diagnostic["executed_provider_calls"] != 0:
        raise ValueError("public pilot must never invoke providers")
    inferred = (
        not call["context_overflow"]
        and type(call["input_tokens"]) is int and call["input_tokens"] > 0
        and type(call["output_tokens"]) is int and call["output_tokens"] > 0
    )
    return {
        "query_id": case["query_id"], "category": case["category"],
        "agreement": _agreement(plan["selected_tools"], case["archived_calls"]),
        "diagnostic": diagnostic, "plan": plan, "understand": call,
        "inference_observed": inferred, "total_wall_s": elapsed,
        "executed_provider_calls": 0,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-tree", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tree = _git(ROOT, "rev-parse", "HEAD:src/schemarouter")
    if tree != args.expected_source_tree:
        raise ValueError("product source differs from the reviewed freeze tree")
    fixture = _load_fixture()
    cases = _cohort(fixture["cases"], "pilot")
    if len(cases) != PILOT_SIZE:
        raise ValueError("pilot denominator changed")
    session, intents, rank = build_original_paper_inventory(fixture["inventory"])
    actor = PrincipalContext(subject="public-original-paper-small-model-pilot")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest = {
        "scope": "public_archived_plan_agreement_only",
        "source_revision": _git(ROOT, "rev-parse", "HEAD"),
        "product_tree": tree, "public_fixture_blob": FIXTURE_BLOB,
        "paper_revision": fixture["provenance"]["commit"],
        "query_ids": [case["query_id"] for case in cases],
        "private_original_repository_used": False,
        "historical_archived_calls_are_gold": False,
        "provider_calls": 0, "answer_accuracy_measured": False,
        "independent_e2": False, "release_qualified": False,
        "complete": False, "actual_model_inference": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    generate, identity = _local_backend()
    manifest["model"] = identity
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    measured = MeasuredModel(generate)
    rows = []
    with args.out.open("w", encoding="utf-8") as out:
        for case in cases:
            row = await _case(session, intents, rank, actor, measured, case)
            out.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            out.flush()
            rows.append(row)
    if len(rows) != PILOT_SIZE:
        raise ValueError("public pilot denominator incomplete")
    manifest.update({
        "complete": True, "observed_rows": len(rows),
        "actual_model_inference": all(row["inference_observed"] for row in rows),
        "inferred_rows": sum(row["inference_observed"] for row in rows),
        "context_overflows": sum(row["understand"]["context_overflow"] for row in rows),
        "agreement": {
            key: mean(row["agreement"][key] for row in rows)
            for key in rows[0]["agreement"]
        },
        "mean_total_wall_s": mean(row["total_wall_s"] for row in rows),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("PUBLIC_MODEL_PILOT", json.dumps(manifest, sort_keys=True), flush=True)
    if not manifest["actual_model_inference"]:
        raise ValueError("one or more rows lacked observed actual model generation")


if __name__ == "__main__":
    asyncio.run(main())

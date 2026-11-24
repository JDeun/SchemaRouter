"""Genuine common-model replay of the pinned original paper's three arms.

No archived plans, gold or reconstructed hints enter the restored Understand
callback. The original fixture retrieval ignores input values: these are
simulated projection-level reader scores, not real provider or independent E2.
The public CPU pilot uses a different checkpoint and generation cap.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import runpy
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAPER_REVISION = "368116746170d6dd0d95a91352daba8abc42ca13"
ORIGINAL_MODEL = "qwen3.5-122b-a10b"
ARMS = ("original_schema_router", "restored_schema_router", "prompt_only")
SOURCE_FILES = {
    "experiments/schema/inventory.json": "71713203dd7145898201868bf1c2435229cdb709",
    "experiments/dataset/queries.jsonl": "ae4c25155b90bb5b7c7f775e8a9bf23fbefe6f95",
    "experiments/routers/schema_router.py": "09d84bda0f7354ce2e46016b74ff12c3ee0fba5c",
    "experiments/answer/run_answer_eval.py": "09753c43018b5731ab7a9128bbf7f9a5e7ce7e54",
    "experiments/evaluator/metrics.py": "d852885ac375485e400115af65caee9c814495a0",
}


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True,
        text=True, timeout=20,
    ).stdout.strip()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _verify_original(path: Path) -> dict[str, str]:
    if _git(path, "rev-parse", "HEAD") != PAPER_REVISION:
        raise ValueError("wrong original paper revision")
    if _git(path, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("modified original paper source")
    hashes = {}
    paths = (
        *SOURCE_FILES, "experiments/dataset/gold_labels.jsonl",
        "experiments/dataset/fixtures.json", "experiments/dataset/answer_keys.json",
        "experiments/common/retrieval.py", "experiments/routers/prompt_only_router.py",
        "experiments/common/llm.py",
    )
    for name in paths:
        data = (path / name).read_bytes()
        blob = hashlib.sha1(
            f"blob {len(data)}\0".encode() + data, usedforsecurity=False,
        ).hexdigest()
        if name in SOURCE_FILES and blob != SOURCE_FILES[name]:
            raise ValueError(f"original blob differs: {name}")
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def _cohort(rows: list[dict], kind: str) -> list[dict]:
    if len(rows) != 110 or len({row["query_id"] for row in rows}) != 110:
        raise ValueError("original query denominator changed")
    if kind == "full":
        return rows
    first: dict[str, dict] = {}
    for row in rows:
        first.setdefault(row["category"], row)
    if len(first) != 9:
        raise ValueError("original categories changed")
    return list(first.values())


def _local_backend():
    from scripts.agent_utility_v7_dev_agent import (
        MODEL_NAME,
        MODEL_REVISION,
        LocalQwenAgent,
        runtime_identity,
    )

    agent = LocalQwenAgent()

    def generate(system: str, user: str, *, max_tokens: int) -> tuple[str, dict, float]:
        result = agent.generate(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], [],
        )
        answer = result["text"].rstrip()
        for marker in (agent.tokenizer.eos_token, "<|im_end|>", "<|endoftext|>"):
            if marker:
                answer = answer.removesuffix(marker).rstrip()
        return answer, {
            "prompt_tokens": result["input_tokens"],
            "completion_tokens": result["output_tokens"],
            "context_overflow": result["context_overflow"],
            "requested_max_tokens": max_tokens,
        }, result["latency_ms"] / 1000

    return generate, {
        "model_id": MODEL_NAME, "model_revision": MODEL_REVISION,
        "backend": "pinned_public_cpu", "same_checkpoint_as_paper": False,
        "effective_generation_cap": 256, **runtime_identity(),
    }


def _original_backend(llm):
    # Require explicit operator-approved destination and credentials, no
    # implicit remote destination or agent/.env fallback.
    base = os.environ.get("VLLM_BASE_URL")
    key = os.environ.get("VLLM_API_KEY")
    if not base or not key or not key.strip():
        raise ValueError("BLOCKED_ORIGINAL_MODEL: approved VLLM_BASE_URL/API_KEY required")
    url = urlsplit(base)
    if url.username or url.password or not url.hostname or url.scheme not in ("https", "http"):
        raise ValueError("invalid operator-approved endpoint")
    if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("remote original model requires HTTPS")
    if llm._MODEL != ORIGINAL_MODEL:
        raise ValueError("original-model mode requires historical requested model identifier")
    original = llm.chat_with_meta

    def generate(system: str, user: str, *, max_tokens: int) -> tuple[str, dict, float]:
        return original(system, user, temperature=0.0, max_tokens=max_tokens)

    return generate, {
        "model_id": ORIGINAL_MODEL, "backend": "operator_approved_original_vllm",
        "same_requested_model_id_as_paper": True,
        "server_weight_revision_attested": False, "same_checkpoint_as_paper": None,
    }


class MeasuredModel:
    def __init__(self, generate):
        self.generate = generate
        self.calls: list[dict[str, Any]] = []
        self.stage = "understand"

    def with_meta(self, system, user, *, temperature=0.0, max_tokens=1024):
        if temperature != 0.0:
            raise ValueError("historical deterministic temperature required")
        answer, usage, latency = self.generate(system, user, max_tokens=max_tokens)
        self.calls.append({
            "stage": self.stage, "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "context_overflow": bool(usage.get("context_overflow", False)),
            "latency_s": latency,
        })
        return answer, usage, latency

    def chat(self, system, user, *, temperature=0.0, max_tokens=2048):
        return self.with_meta(system, user, temperature=temperature, max_tokens=max_tokens)[0]

    def understand(self, payload):
        if "schema_catalog" in payload or "offered_concepts" in payload:
            raise ValueError("schema-independent Understand boundary violated")
        return self.chat(
            "Return only the single JSON object requested by the input contract.",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        )


async def _current_plan(session, intents, rank, actor, model, query):
    from schemarouter.errors import ModelAnalysisError, PolicyViolationError

    try:
        plan = await session.acompile_query(
            query["query"], principal=actor, intent_registry=intents,
            rank_policy=rank, model=model.understand,
            model_visible_intent_ids=tuple(intent.intent_id for intent in intents.intents),
        )
    except (ModelAnalysisError, PolicyViolationError) as exc:
        return {"query_id": query["query_id"], "selected_tools": [],
                "errors": [type(exc).__name__]}, {
            "status": type(exc).__name__, "coverage_complete": False,
            "strict_missing_required": None, "executed_provider_calls": 0,
        }
    if plan.executable_authority or plan.bindings or len(plan.calls) > 5:
        raise ValueError("unexpected execution authority or width")
    selected = []
    for call in plan.calls:
        if call.call.arguments:
            raise ValueError("model-only replay supplied host arguments")
        selected.append({
            "tool": call.call.tool, "endpoint": call.route_id,
            "parameters": dict(call.parameter_proposals),  # proposals ONLY
            "fields": list(call.call.fields),
            "evidence_requirements": {
                "source_type": call.source_type, "license": call.license,
                "unit_required": any(meta.unit is not None for meta in call.fields_meta),
            },
        })
    return {"query_id": query["query_id"], "selected_tools": selected, "errors": []}, {
        "status": plan.status, "coverage_complete": bool(plan.coverage and plan.coverage.complete),
        "uncovered": [
            item.model_dump(mode="json") for item in plan.coverage.uncovered
        ] if plan.coverage else [],
        "strict_missing_required": sum(len(c.call.missing_required_arguments) for c in plan.calls),
        "executed_provider_calls": 0, "understanding": plan.understanding_hints,
    }


def _missing_required(plan, inventory):
    apis = {api["name"]: api for api in inventory["apis"]}
    return sum(
        sum(bool(p["required"] and p["name"] not in call.get("parameters", {}))
            for p in apis[call["tool"]]["parameters"])
        for call in plan.get("selected_tools", []) if call.get("tool") in apis
    )


def _totals(rows):
    result = {}
    for arm in ARMS:
        subset = [row for row in rows if row["arm"] == arm]
        if not subset:
            continue
        result[arm] = {
            "n": len(subset),
            "tool_exact": mean(row["metrics"]["tool_exact"] for row in subset),
            "field_f1": mean(row["metrics"]["field_f1"] for row in subset),
            "field_recall": mean(row["metrics"]["field_recall"] for row in subset),
            "answer_accuracy": mean(row["correct"] for row in subset),
            "deterministic_answer_accuracy": mean(row["correct_deterministic"] for row in subset),
            "mean_total_latency_s": mean(row["total_wall_s"] for row in subset),
            "mean_reader_prompt_tokens": mean(row["reader_prompt_tokens"] for row in subset)
            if all(type(row["reader_prompt_tokens"]) is int for row in subset) else None,
            "mean_total_prompt_tokens": mean(row["total_prompt_tokens"] for row in subset)
            if all(type(row["total_prompt_tokens"]) is int for row in subset) else None,
            "model_calls": sum(len(row["model_calls"]) for row in subset),
            "strict_missing_parameter_rows": sum(
                row["missing_required_proposals"] > 0 for row in subset
            ),
            "route_statuses": dict(Counter(row["diagnostic"]["status"] for row in subset)),
        }
    return result


def _valid_plan_shape(plan):
    return (
        type(plan) is dict and type(plan.get("selected_tools")) is list
        and all(type(call) is dict and type(call.get("tool")) is str
                and type(call.get("fields")) is list
                and all(type(field) is str for field in call["fields"])
                and type(call.get("parameters")) is dict
                and type(call.get("evidence_requirements")) is dict
                for call in plan["selected_tools"])
    )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-root", type=Path, required=True)
    parser.add_argument("--backend", choices=("local-qwen", "original-vllm"), required=True)
    parser.add_argument("--cohort", choices=("pilot", "full"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paper = args.paper_root.resolve()
    hashes = _verify_original(paper)
    fixture = runpy.run_path(str(ROOT / "tests/test_original_paper_full_replay.py"))
    inventory = json.loads((paper / "experiments/schema/inventory.json").read_text())
    if inventory != fixture["FIXTURE"]["inventory"]:
        raise ValueError("current fixture inventory differs from original")
    session, intents, rank = fixture["_build"]()
    actor = fixture["ACTOR"]
    queries = _cohort(_jsonl(paper / "experiments/dataset/queries.jsonl"), args.cohort)
    sys.path.insert(0, str(paper))
    llm = importlib.import_module("experiments.common.llm")
    generate, identity = (
        _local_backend() if args.backend == "local-qwen" else _original_backend(llm)
    )
    measured = MeasuredModel(generate)
    llm.chat = measured.chat
    llm.chat_with_meta = measured.with_meta
    old = importlib.import_module("experiments.routers.schema_router")
    baseline = importlib.import_module("experiments.routers.prompt_only_router")
    old_router = old.SchemaRouter()
    full_router = baseline.PromptOnlyRouter()
    answer = importlib.import_module("experiments.answer.run_answer_eval")
    retrieval = importlib.import_module("experiments.common.retrieval")
    evaluator = importlib.import_module("experiments.evaluator.metrics")
    gold = {row["query_id"]: row for row in _jsonl(
        paper / "experiments/dataset/gold_labels.jsonl",
    )}
    keys = json.loads((paper / "experiments/dataset/answer_keys.json").read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    manifest = {
        "paper_revision": PAPER_REVISION, "source_hashes": hashes,
        "source_revision": _git(ROOT, "rev-parse", "HEAD"), "model": identity,
        "cohort": args.cohort, "query_ids": [q["query_id"] for q in queries],
        "arms": ARMS, "temperature": 0.0, "thinking": False,
        "actual_model_inference": False, "complete": False,
        "simulated_retrieval": True, "retrieval_checks_arguments": False,
        "independent_e2": False, "release_qualified": False,
    }
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with args.out.open("w", encoding="utf-8") as out:
        for position, query in enumerate(queries):
            qid = query["query_id"]
            order = ARMS[position % len(ARMS):] + ARMS[:position % len(ARMS)]
            for arm in order:
                measured.calls.clear()
                measured.stage = "understand"
                started = time.monotonic()
                raw_query = {"query_id": qid, "query": query["query"]}
                if arm == "restored_schema_router":
                    plan, diagnostic = await _current_plan(
                        session, intents, rank, actor, measured, raw_query,
                    )
                else:
                    router = old_router if arm == "original_schema_router" else full_router
                    try:
                        plan = router.route(raw_query)
                    except (ValueError, TypeError, AttributeError, KeyError) as exc:
                        plan = {"query_id": qid, "selected_tools": [],
                                "errors": [type(exc).__name__]}
                    if not _valid_plan_shape(plan):
                        plan = {"query_id": qid, "selected_tools": [],
                                "errors": ["malformed_original_plan"]}
                    diagnostic = {"status": "plan_error" if plan.get("errors") else "planned"}
                if len(measured.calls) != 1:
                    raise ValueError("no actual model understanding receipt")
                metrics = evaluator.evaluate_one(plan, gold[qid])
                context = retrieval.simulate_retrieval(qid, plan)
                measured.stage = "reader"
                text, usage, _ = measured.with_meta(
                    answer._SYSTEM, f"[검색 결과]\n{context or '(없음)'}\n\n[질의]\n{query['query']}",
                )
                wall = time.monotonic() - started
                measured.stage = "judge"
                correct = answer.llm_judge(query["query"], text, keys[qid])
                if len(measured.calls) != 3:
                    raise ValueError("missing actual reader/judge model receipt")
                calls = list(measured.calls)
                row = {
                    "query_id": qid, "category": query["category"], "arm": arm,
                    "metrics": metrics, "diagnostic": diagnostic, "plan": plan,
                    "correct": int(correct),
                    "correct_deterministic": int(answer.judge(text, keys[qid])),
                    "reader_prompt_tokens": usage.get("prompt_tokens"),
                    "total_prompt_tokens": sum(c["input_tokens"] for c in calls[:2])
                    if all(type(c["input_tokens"]) is int for c in calls[:2]) else None,
                    "total_wall_s": wall, "model_calls": calls,
                    "missing_required_proposals": _missing_required(plan, inventory),
                    "answer": text[:600], "executed_provider_calls": 0,
                }
                out.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                out.flush()
                rows.append(row)
                print("PAPER_MODEL_ROW", qid, arm, metrics["tool_exact"],
                      metrics["field_f1"], row["correct"], diagnostic["status"], flush=True)
    if len(rows) != len(queries) * len(ARMS):
        raise ValueError("missing model rows")
    manifest.update({
        "actual_model_inference": True, "complete": True,
        "observed_rows": len(rows), "summary": _totals(rows),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PAPER_MODEL_SUMMARY " + json.dumps(manifest["summary"], sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())

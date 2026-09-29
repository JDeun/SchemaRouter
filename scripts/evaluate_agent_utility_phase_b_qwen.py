"""Phase B1: local Qwen3 agent A/B over FULL vs SchemaRouter candidate sets."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v1_catalog import (  # noqa: E402
    CATALOG_SIZES,
    TASKS,
    build_registry,
    route_ids,
)
from benchmarks.agent_utility_v1_executor import (  # noqa: E402
    DeterministicTaskExecutor,
)
from scripts.evaluate_agent_utility_phase_a import _rank  # noqa: E402

MODEL_NAME = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
MAX_NEW_TOKENS = 256
MAX_TURNS = 6
SEED = 20260929
THREADS = 4
TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    flags=re.DOTALL,
)

SYSTEM_PROMPT = """You are a tool-using agent.
Solve the user's task using only the provided registered tools.
Never invent a tool name or hidden capability.
Use tool results when later calls depend on earlier outputs.
When the required capability is not available among the provided tools,
respond with exactly REQUEST_MORE_TOOLS.
Do not claim completion before the requested task is actually complete.
Destructive tools are subject to executor policy and cannot bypass approval.
"""


def _endpoint_lookup(registry: Any) -> dict[str, tuple[Any, Any]]:
    return {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }


def _function_name(route_id: str) -> str:
    return route_id.replace(".", "__")


def _function_tool(
    route_id: str,
    tool: Any,
    endpoint: Any,
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for parameter in endpoint.parameters:
        schema = dict(parameter.json_schema)
        if parameter.description:
            schema["description"] = parameter.description
        properties[parameter.name] = schema
        if parameter.required:
            required.append(parameter.name)

    output_bits: list[str] = []
    for field in endpoint.output_fields:
        bit = field.semantic_id or field.name
        if field.unit:
            bit += f" unit={field.unit}"
        if field.unit_normalization is not None:
            bit += (
                f" dimension={field.unit_normalization.dimension}"
                f" canonical_unit={field.unit_normalization.canonical_unit}"
            )
        output_bits.append(bit)

    description_parts = [
        tool.description.strip(),
        endpoint.description.strip(),
        f"Registered route: {route_id}.",
        f"read_only={endpoint.read_only}; destructive={endpoint.destructive}.",
    ]
    if output_bits:
        description_parts.append("Outputs: " + "; ".join(output_bits) + ".")

    return {
        "type": "function",
        "function": {
            "name": _function_name(route_id),
            "description": " ".join(
                part for part in description_parts if part
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _visible_tools(
    registry: Any,
    selected_routes: list[str],
) -> list[dict[str, Any]]:
    lookup = _endpoint_lookup(registry)
    return [
        _function_tool(route_id, *lookup[route_id])
        for route_id in sorted(selected_routes)
    ]


def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in TOOL_CALL_RE.finditer(text):
        payload = json.loads(match.group(1))
        if not isinstance(payload, dict):
            raise ValueError("tool call payload must be an object")
        name = payload.get("name")
        arguments = payload.get("arguments", {})
        if not isinstance(name, str) or not name:
            raise ValueError("tool call name must be a non-empty string")
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if not isinstance(arguments, dict):
            raise ValueError("tool call arguments must be an object")
        calls.append({"name": name, "arguments": arguments})
    return calls


def _tool_response_message(observations: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tool_response>\n"
        + json.dumps(observation, ensure_ascii=False, sort_keys=True)
        + "\n</tool_response>"
        for observation in observations
    )


class LocalQwenAgent:
    def __init__(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            revision=MODEL_REVISION,
            trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            revision=MODEL_REVISION,
            trust_remote_code=False,
            torch_dtype=torch.float32,
            device_map=None,
        )
        self.model.eval()
        self.context_limit = int(
            getattr(self.model.config, "max_position_embeddings", 32768)
        )

    def _render(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> tuple[str, int, int]:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tools=tools,
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=False,
        )
        without_tools = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=False,
        )
        input_ids = self.tokenizer(
            prompt,
            add_special_tokens=False,
            return_tensors="pt",
        )["input_ids"]
        plain_ids = self.tokenizer(
            without_tools,
            add_special_tokens=False,
            return_tensors="pt",
        )["input_ids"]
        input_tokens = int(input_ids.shape[-1])
        tool_tokens = max(0, input_tokens - int(plain_ids.shape[-1]))
        return prompt, input_tokens, tool_tokens

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt, input_tokens, tool_tokens = self._render(messages, tools)
        if input_tokens + MAX_NEW_TOKENS > self.context_limit:
            return {
                "text": "",
                "input_tokens": input_tokens,
                "tool_tokens": tool_tokens,
                "output_tokens": 0,
                "latency_ms": 0.0,
                "context_overflow": True,
            }

        encoded = self.tokenizer(
            prompt,
            add_special_tokens=False,
            return_tensors="pt",
        )
        started = time.perf_counter_ns()
        with self.torch.no_grad():
            output = self.model.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=MAX_NEW_TOKENS,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        generated = output[0, encoded["input_ids"].shape[-1] :]
        text = self.tokenizer.decode(
            generated,
            skip_special_tokens=False,
        )
        return {
            "text": text,
            "input_tokens": input_tokens,
            "tool_tokens": tool_tokens,
            "output_tokens": int(generated.shape[-1]),
            "latency_ms": elapsed_ms,
            "context_overflow": False,
        }


def _candidate_set(
    registry: Any,
    query: str,
    condition: str,
    required_routes: tuple[str, ...],
) -> list[str]:
    if condition == "FULL":
        return sorted(route_ids(registry))
    if condition == "ORACLE":
        return sorted(required_routes)
    if condition.startswith("SR-"):
        k = int(condition.split("-", 1)[1])
        ranked = _rank(registry, query)
        return sorted(str(row["route_id"]) for row in ranked[:k])
    raise ValueError(condition)


def _run_fixed_episode(
    agent: LocalQwenAgent,
    registry: Any,
    task: Any,
    condition: str,
) -> dict[str, Any]:
    visible_routes = _candidate_set(
        registry,
        task.query,
        condition,
        task.required_routes,
    )
    return _run_episode(
        agent,
        registry,
        task,
        condition,
        initial_routes=visible_routes,
        progressive=False,
    )


def _run_progressive_episode(
    agent: LocalQwenAgent,
    registry: Any,
    task: Any,
) -> dict[str, Any]:
    ranked = _rank(registry, task.query)
    ranking = [str(row["route_id"]) for row in ranked]
    stages = [
        sorted(ranking[:3]),
        sorted(ranking[:10]),
        sorted(route_ids(registry)),
    ]
    return _run_episode(
        agent,
        registry,
        task,
        "SR-PROGRESSIVE",
        initial_routes=stages[0],
        progressive=True,
        progressive_stages=stages,
    )


def _run_episode(
    agent: LocalQwenAgent,
    registry: Any,
    task: Any,
    condition: str,
    *,
    initial_routes: list[str],
    progressive: bool,
    progressive_stages: list[list[str]] | None = None,
) -> dict[str, Any]:
    executor = DeterministicTaskExecutor(registry, task.task_id)
    if progressive and progressive_stages is None:
        raise ValueError("progressive stages are required")
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task.query},
    ]
    visible_routes = list(initial_routes)
    stage_index = 0
    expansions = 0
    candidate_history = [list(visible_routes)]
    turn_rows: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0
    total_tool_tokens = 0
    total_latency = 0.0
    context_overflow = False
    final_text = ""
    malformed_calls = 0

    for turn in range(1, MAX_TURNS + 1):
        tools = _visible_tools(registry, visible_routes)
        generated = agent.generate(messages, tools)
        total_input += int(generated["input_tokens"])
        total_output += int(generated["output_tokens"])
        total_tool_tokens += int(generated["tool_tokens"])
        total_latency += float(generated["latency_ms"])

        if generated["context_overflow"]:
            context_overflow = True
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": "context_overflow",
                }
            )
            break

        text = str(generated["text"])
        final_text = text
        calls: list[dict[str, Any]]
        try:
            calls = _parse_tool_calls(text)
        except Exception as exc:  # noqa: BLE001
            calls = []
            malformed_calls += 1
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": f"malformed_tool_call:{type(exc).__name__}",
                }
            )
            if progressive and stage_index < 2:
                stage_index += 1
                expansions += 1
                visible_routes = list(progressive_stages[stage_index])
                candidate_history.append(list(visible_routes))
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {"role": "user", "content": "TASK_INCOMPLETE"}
                )
                continue
            break

        if not calls:
            event = "final"
            turn_rows.append(
                {
                    "turn": turn,
                    "candidate_count": len(visible_routes),
                    **generated,
                    "tool_calls": [],
                    "event": event,
                }
            )
            if executor.complete:
                break
            request_more = text.strip() == "REQUEST_MORE_TOOLS"
            if progressive and stage_index < 2:
                stage_index += 1
                expansions += 1
                visible_routes = list(progressive_stages[stage_index])
                candidate_history.append(list(visible_routes))
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {"role": "user", "content": "TASK_INCOMPLETE"}
                )
                continue
            if request_more:
                break
            break

        messages.append({"role": "assistant", "content": text})
        observations: list[dict[str, Any]] = []
        serialized_calls: list[dict[str, Any]] = []
        had_failure = False

        for call in calls:
            name = str(call["name"])
            route_id = name.replace("__", ".", 1)
            arguments = dict(call["arguments"])
            attempt = executor.execute(
                route_id,
                arguments,
                available=route_id in visible_routes,
            )
            serialized_calls.append(
                {
                    "name": name,
                    "route_id": route_id,
                    "arguments": arguments,
                    "attempt": asdict(attempt),
                }
            )
            observations.append(attempt.observation)
            if attempt.error is not None or attempt.policy_blocked:
                had_failure = True

        turn_rows.append(
            {
                "turn": turn,
                "candidate_count": len(visible_routes),
                **generated,
                "tool_calls": serialized_calls,
                "event": "tool_calls",
            }
        )
        messages.append(
            {
                "role": "user",
                "content": _tool_response_message(observations),
            }
        )

        if progressive and had_failure and stage_index < 2:
            stage_index += 1
            expansions += 1
            visible_routes = list(progressive_stages[stage_index])
            candidate_history.append(list(visible_routes))

    attempts = executor.attempts
    valid_schema_calls = sum(attempt.schema_valid for attempt in attempts)
    valid_semantic_calls = sum(
        attempt.schema_valid and attempt.semantic_valid
        for attempt in attempts
    )
    required_advanced = sum(attempt.advanced_task for attempt in attempts)
    extraneous = sum(
        attempt.schema_valid
        and not attempt.expected_at_step
        and not attempt.policy_blocked
        for attempt in attempts
    )
    failures = sum(attempt.error is not None for attempt in attempts)
    policy_blocks = sum(attempt.policy_blocked for attempt in attempts)

    destructive_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
        if bool(endpoint.destructive)
    }
    destructive_attempts = sum(
        attempt.route_id in destructive_routes
        for attempt in attempts
    )
    unauthorized_destructive = sum(
        attempt.route_id in destructive_routes
        and not attempt.expected_at_step
        and not attempt.policy_blocked
        for attempt in attempts
    )

    final_answer_present = bool(
        final_text.strip()
        and "<tool_call>" not in final_text
        and final_text.strip() != "REQUEST_MORE_TOOLS"
    )
    return {
        "task_id": task.task_id,
        "kind": task.kind,
        "condition": condition,
        "passed": executor.complete and not context_overflow,
        "task_complete": executor.complete,
        "required_routes": list(task.required_routes),
        "required_routes_advanced": required_advanced,
        "required_route_call_coverage": (
            required_advanced / len(task.required_routes)
        ),
        "turns": len(turn_rows),
        "expansions": expansions,
        "candidate_history": candidate_history,
        "initial_candidate_count": len(initial_routes),
        "final_candidate_count": len(visible_routes),
        "context_overflow": context_overflow,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "tool_schema_tokens": total_tool_tokens,
        "latency_ms": total_latency,
        "tool_call_count": len(attempts),
        "schema_valid_call_rate": (
            valid_schema_calls / len(attempts) if attempts else None
        ),
        "semantic_valid_call_rate": (
            valid_semantic_calls / len(attempts) if attempts else None
        ),
        "extraneous_tool_calls": extraneous,
        "failed_executions": failures,
        "destructive_attempts": destructive_attempts,
        "policy_blocks": policy_blocks,
        "unauthorized_destructive_executions": unauthorized_destructive,
        "malformed_tool_calls": malformed_calls,
        "final_answer_present": final_answer_present,
        "final_text": final_text,
        "attempts": [asdict(attempt) for attempt in attempts],
        "turn_rows": turn_rows,
    }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = 0.95 * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [row for row in rows if row["tool_call_count"] > 0]
    single = [row for row in rows if row["kind"] == "single"]
    multi = [row for row in rows if row["kind"] == "multi"]
    return {
        "episodes": len(rows),
        "task_pass_rate": sum(row["passed"] for row in rows) / len(rows),
        "single_task_pass_rate": (
            sum(row["passed"] for row in single) / len(single)
            if single
            else None
        ),
        "multi_task_pass_rate": (
            sum(row["passed"] for row in multi) / len(multi)
            if multi
            else None
        ),
        "required_route_call_coverage": statistics.fmean(
            float(row["required_route_call_coverage"]) for row in rows
        ),
        "mean_input_tokens": statistics.fmean(
            float(row["input_tokens"]) for row in rows
        ),
        "mean_output_tokens": statistics.fmean(
            float(row["output_tokens"]) for row in rows
        ),
        "mean_tool_schema_tokens": statistics.fmean(
            float(row["tool_schema_tokens"]) for row in rows
        ),
        "mean_turns": statistics.fmean(float(row["turns"]) for row in rows),
        "mean_tool_calls": statistics.fmean(
            float(row["tool_call_count"]) for row in rows
        ),
        "mean_expansions": statistics.fmean(
            float(row["expansions"]) for row in rows
        ),
        "latency_ms_median": statistics.median(
            float(row["latency_ms"]) for row in rows
        ),
        "latency_ms_p95": _p95(
            [float(row["latency_ms"]) for row in rows]
        ),
        "context_overflow_rate": sum(
            row["context_overflow"] for row in rows
        )
        / len(rows),
        "schema_valid_call_rate": (
            statistics.fmean(
                float(row["schema_valid_call_rate"])
                for row in calls
                if row["schema_valid_call_rate"] is not None
            )
            if calls
            else None
        ),
        "semantic_valid_call_rate": (
            statistics.fmean(
                float(row["semantic_valid_call_rate"])
                for row in calls
                if row["semantic_valid_call_rate"] is not None
            )
            if calls
            else None
        ),
        "extraneous_tool_calls": sum(
            int(row["extraneous_tool_calls"]) for row in rows
        ),
        "failed_executions": sum(
            int(row["failed_executions"]) for row in rows
        ),
        "policy_blocks": sum(int(row["policy_blocks"]) for row in rows),
        "unauthorized_destructive_executions": sum(
            int(row["unauthorized_destructive_executions"])
            for row in rows
        ),
        "malformed_tool_calls": sum(
            int(row["malformed_tool_calls"]) for row in rows
        ),
        "final_answer_present_rate": sum(
            row["final_answer_present"] for row in rows
        )
        / len(rows),
    }


def _bootstrap_delta(
    full_rows: list[dict[str, Any]],
    condition_rows: list[dict[str, Any]],
    *,
    iterations: int = 5000,
) -> dict[str, float]:
    by_key_full = {
        (int(row["catalog_size"]), str(row["task_id"])): bool(row["passed"])
        for row in full_rows
    }
    by_key_cond = {
        (int(row["catalog_size"]), str(row["task_id"])): bool(row["passed"])
        for row in condition_rows
    }
    keys = sorted(set(by_key_full).intersection(by_key_cond))
    if not keys:
        return {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0}

    paired = [
        int(by_key_cond[key]) - int(by_key_full[key])
        for key in keys
    ]
    delta = statistics.fmean(paired)
    rng = random.Random(SEED)
    samples: list[float] = []
    for _ in range(iterations):
        samples.append(
            statistics.fmean(
                paired[rng.randrange(len(paired))]
                for _ in range(len(paired))
            )
        )
    samples.sort()

    def q(prob: float) -> float:
        pos = prob * (len(samples) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        if lo == hi:
            return samples[lo]
        weight = pos - lo
        return samples[lo] * (1 - weight) + samples[hi] * weight

    return {
        "delta": delta,
        "ci_low": q(0.025),
        "ci_high": q(0.975),
    }


def evaluate(
    *,
    catalog_sizes: tuple[int, ...],
    task_ids: set[str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    agent = LocalQwenAgent()
    model_load_ms = (time.perf_counter_ns() - started) / 1_000_000

    conditions = ("FULL", "SR-3", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE")
    rows: list[dict[str, Any]] = []

    for size in catalog_sizes:
        registry = build_registry(size)
        for task in TASKS:
            if task_ids is not None and task.task_id not in task_ids:
                continue
            for condition in conditions:
                if condition == "SR-PROGRESSIVE":
                    row = _run_progressive_episode(agent, registry, task)
                else:
                    row = _run_fixed_episode(
                        agent,
                        registry,
                        task,
                        condition,
                    )
                row["catalog_size"] = size
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "catalog_size": size,
                            "task_id": task.task_id,
                            "condition": condition,
                            "passed": row["passed"],
                            "turns": row["turns"],
                            "tokens": row["input_tokens"] + row["output_tokens"],
                            "overflow": row["context_overflow"],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    flush=True,
                )

    summaries: dict[str, Any] = {}
    for size in catalog_sizes:
        summaries[str(size)] = {}
        for condition in conditions:
            subset = [
                row
                for row in rows
                if row["catalog_size"] == size
                and row["condition"] == condition
            ]
            summaries[str(size)][condition] = _summary(subset)

    overall: dict[str, Any] = {}
    for condition in conditions:
        subset = [row for row in rows if row["condition"] == condition]
        overall[condition] = _summary(subset)

    full_rows = [row for row in rows if row["condition"] == "FULL"]
    paired_deltas = {}
    for condition in ("SR-3", "SR-5", "SR-10", "SR-PROGRESSIVE"):
        paired_deltas[condition] = _bootstrap_delta(
            full_rows,
            [row for row in rows if row["condition"] == condition],
        )

    progressive_rows = [
        row for row in rows if row["condition"] == "SR-PROGRESSIVE"
    ]
    initial_miss = [
        row
        for row in progressive_rows
        if not set(row["required_routes"]).issubset(
            set(row["candidate_history"][0])
        )
    ]
    recovered = [row for row in initial_miss if row["passed"]]

    return {
        "experiment": "0.14-agent-utility-phase-b1-qwen3-0.6b",
        "issue": 420,
        "model": {
            "name": MODEL_NAME,
            "revision": MODEL_REVISION,
            "dtype": "float32",
            "device": "cpu",
            "max_new_tokens": MAX_NEW_TOKENS,
            "max_turns": MAX_TURNS,
            "seed": SEED,
            "threads": THREADS,
            "context_limit": agent.context_limit,
            "enable_thinking": False,
        },
        "model_load_ms": model_load_ms,
        "catalog_sizes": list(catalog_sizes),
        "task_ids": sorted(task_ids) if task_ids is not None else None,
        "rows": rows,
        "summary_by_catalog": summaries,
        "overall": overall,
        "paired_task_pass_delta_vs_full": paired_deltas,
        "progressive_recovery": {
            "initial_required_set_miss_count": len(initial_miss),
            "recovered_count": len(recovered),
            "recovery_rate": (
                len(recovered) / len(initial_miss) if initial_miss else None
            ),
        },
        "policy": {
            "qwen_is_downstream_agent_only": True,
            "schemarouter_rank_scores_visible_to_agent": False,
            "candidate_routes_lexically_sorted": True,
            "task_ground_truth_visible_to_agent": False,
            "silent_truncation": False,
            "full_context_overflow_is_failure": True,
            "unauthorized_destructive_execution_allowed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--catalog-sizes",
        type=str,
        default=",".join(str(size) for size in CATALOG_SIZES),
    )
    parser.add_argument(
        "--task-ids",
        type=str,
        default="",
        help="Comma-separated task IDs for mechanical smoke only.",
    )
    args = parser.parse_args()

    catalog_sizes = tuple(
        int(value)
        for value in args.catalog_sizes.split(",")
        if value.strip()
    )
    invalid = sorted(set(catalog_sizes).difference(CATALOG_SIZES))
    if invalid:
        raise ValueError(f"unsupported catalog sizes: {invalid}")

    task_ids = {
        value.strip()
        for value in args.task_ids.split(",")
        if value.strip()
    } or None

    result = evaluate(catalog_sizes=catalog_sizes, task_ids=task_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "overall": result["overall"],
                "paired_task_pass_delta_vs_full": result[
                    "paired_task_pass_delta_vs_full"
                ],
                "progressive_recovery": result["progressive_recovery"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

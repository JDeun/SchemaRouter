"""Owner-authored Qwen3.5 GGUF E1 pilot with locally loaded original tool fixtures.

This does NOT qualify as independent E2. Native model inference requires a
user-installed llama-cpp-python backend and an explicitly downloaded GGUF
file; never downloads a model or calls an external model endpoint implicitly.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.agent_utility_v7_dev_agent import _as_openai_tools
from scripts.research_codegraph_local_multiroute_e1 import (
    LANGUAGE_ALIASES, ROOT, run_local_multiroute_codegraph_e1,
)
from scripts.research_qwen35_native_tool_adapter_e1 import normalize_qwen35_xml_action
from scripts.research_real_qwen_bound_two_step_e0 import _parse_strict_model_json

# These are filename contracts for externally reviewed Q4_K_M quantizations.
# The originating HF model revision and *full file sha256* are report receipts.
# GGUF results are not directly checkpoint/precision equivalent to Qwen3 FP32.
MODELS = {
    "qwen35_2b": ("gguf/Qwen3.5-2B-GGUF", "qwen3.5-2b-Q4_K_M.gguf"),
    "qwen35_4b": ("gguf/Qwen3.5-4B-GGUF", "qwen3.5-4b-Q4_K_M.gguf"),
}
MAX_NEW_TOKENS = 256
MAX_TURNS = 5
THREADS = 4
SEED = 20260929
_FORMAT_OVERRIDE = (
    "Model-facing wire format: use your native Qwen3.5 tool-call XML "
    "(<tool_call><function=name><parameter=key>value</parameter>"
    "</function></tool_call>). Any other instructions that mention "
    "JSON inside a tool_call refer only to the trusted host protocol. "
    "Choose tools yourself; never invent arguments or source results."
)
_CANONICAL = re.compile(r"<tool_call>(\{.*\})</tool_call>", re.DOTALL)


def _to_native_chat(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert *already host-accepted* previous calls to OpenAI chat history."""
    rendered: list[dict[str, Any]] = []
    last_call_id: str | None = None
    for i, item in enumerate(messages):
        role, content = item["role"], item["content"]
        if role == "assistant":
            candidate = _CANONICAL.fullmatch(content.strip())
            if candidate is None:
                rendered.append({"role": role, "content": content})
                continue
            action = _parse_strict_model_json(candidate.group(1))
            if (
                type(action) is not dict or set(action) != {"name", "arguments"}
                or type(action["name"]) is not str
                or type(action["arguments"]) is not dict
            ):
                raise ValueError("untrusted host model history")
            last_call_id = f"research_call_{i}"
            rendered.append({
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": last_call_id, "type": "function",
                    "function": {
                        "name": action["name"],
                        "arguments": json.dumps(
                            action["arguments"], ensure_ascii=False, allow_nan=False,
                            separators=(",", ":"),
                        ),
                    },
                }],
            })
        elif role == "tool":
            if last_call_id is None:
                raise ValueError("unpaired original tool observation in history")
            rendered.append({
                "role": "tool", "tool_call_id": last_call_id,
                "content": content,
            })
            last_call_id = None
        elif role in ("system", "user"):
            if role == "system":
                content += "\n" + _FORMAT_OVERRIDE
            rendered.append({"role": role, "content": content})
        else:
            raise ValueError("unexpected model-facing message role")
    if last_call_id is not None:
        raise ValueError("unpaired original function call")
    return rendered


def _strict_native_response(message: dict[str, Any], tools: list[dict[str, Any]]) -> str:
    """Normalize one original offered model proposal, never execute it."""
    content = message.get("content")
    calls = message.get("tool_calls") or []
    if type(calls) is not list:
        raise ValueError("invalid native tool call list")
    if calls:
        if len(calls) != 1 or content not in (None, ""):
            raise ValueError("multiple or mixed native tool actions")
        tool = calls[0]
        if (
            type(tool) is not dict
            or tool.get("type") != "function"
            or type(tool.get("function")) is not dict
        ):
            raise ValueError("malformed structured native function")
        fn = tool["function"]
        name, args_json = fn.get("name"), fn.get("arguments")
        if (
            type(name) is not str or name not in [t["name"] for t in tools]
            or type(args_json) is not str
        ):
            raise ValueError("unknown native function or arguments")
        args = _parse_strict_model_json(args_json)
        if type(args) is not dict:
            raise ValueError("nonobject native arguments")
        return "<tool_call>" + json.dumps(
            {"name": name, "arguments": args},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ) + "</tool_call>"
    if type(content) is not str:
        raise ValueError("no native assistant content")
    text, _ = normalize_qwen35_xml_action(content, offered_tools=tools)
    return text


class Qwen35LocalGGUFAgent:
    """Local CPU llama.cpp GGUF backend; original host still owns all calls."""

    def __init__(self, model_file: Path, *, n_ctx: int = 8192) -> None:
        if not model_file.is_file() or model_file.suffix != ".gguf":
            raise ValueError("pre-downloaded local GGUF file required")
        if type(n_ctx) is not int or not 1024 <= n_ctx <= 16384:
            raise ValueError("bounded GGUF model context required")
        from llama_cpp import Llama

        self.engine = Llama(
            model_path=str(model_file), n_ctx=n_ctx, n_threads=THREADS,
            n_gpu_layers=0, seed=SEED, verbose=False,
        )

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompts = _to_native_chat(messages)
        if type(tools) is not list:
            raise ValueError("host native tool definitions required")
        started = time.perf_counter_ns()
        response = self.engine.create_chat_completion(
            messages=prompts,
            tools=_as_openai_tools(tools) if tools else None,
            tool_choice="auto" if tools else "none",
            temperature=0.0,
            top_p=1.0,
            max_tokens=MAX_NEW_TOKENS,
            stream=False,
        )
        latency = (time.perf_counter_ns() - started) / 1_000_000
        if type(response) is not dict or type(response.get("usage")) is not dict:
            raise ValueError("original model token receipts absent")
        usage = response["usage"]
        inputs, outputs = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if (
            type(inputs) is not int or type(outputs) is not int
            or inputs < 0 or outputs < 0
        ):
            raise ValueError("invalid model token receipts")
        choices = response.get("choices")
        if type(choices) is not list or len(choices) != 1:
            raise ValueError("ambiguous model generation")
        msg = choices[0].get("message")
        if type(msg) is not dict or not math.isfinite(latency):
            raise ValueError("missing native model response")
        try:
            canonical = _strict_native_response(msg, tools)
        except (ValueError, TypeError, OverflowError):
            # Preserve fail-closed, model-attributable malformed grammar
            # as a strict parser failure, never a trusted source operation.
            canonical = "<tool_call>"
        return {
            "text": canonical, "context_overflow": False,
            "input_tokens": inputs,
            # Unknown subset, NOT a measured zero. The runner explicitly
            # masks tool_schema_tokens for every returned arm.
            "tool_tokens": 0,
            "output_tokens": outputs,
            "latency_ms": latency,
        }


async def evaluate_qwen35_local_pilot(
    agent: Any, *, language: str, model_variant: str,
    gguf_path: Path, source_repository: str, source_revision: str,
) -> dict[str, Any]:
    if model_variant not in MODELS or language not in LANGUAGE_ALIASES:
        raise ValueError("unregistered pilot model/language")
    if source_repository != MODELS[model_variant][0]:
        raise ValueError("GGUF source repository is not the preregistered one")
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ValueError("immutable source repository revision required")
    if not gguf_path.is_file() or gguf_path.name != MODELS[model_variant][1]:
        raise ValueError("source-qualified GGUF filename required")
    with gguf_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    result = await run_local_multiroute_codegraph_e1(
        agent, language=language, condition="joined", catalog_size=4,
        diagnose_model_actions=True,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
        experimental_graph_frontier=True,
    )
    if (
        result["status"] != "E1_MEASURED_LOCAL_FIVE_ARM_NOT_E2"
        or len(result["outcomes"]) != 5
        or result["source_route_count"] != 4
    ):
        raise ValueError("incomparable original four-route E1 task")
    return {
        **result,
        "study": "CODEGRAPH_QWEN35_Q4_GGUF_PAIRED_LOCAL_E1",
        "model_id": f"Qwen/Qwen3.5-{model_variant.rsplit('_', 1)[-1].upper()}",
        "model_revision": source_revision,
        "gguf_repository": source_repository,
        "gguf_file": gguf_path.name,
        "gguf_sha256": digest,
        "quantization": "Q4_K_M",
        "generation_max_new_tokens": MAX_NEW_TOKENS,
        "token_subset_breakdown_available": False,
        "outcomes": [
            {**row, "tool_schema_tokens": None}
            for row in result["outcomes"]
        ],
        "true_native_local_gguf_execution": True,
        "source_disjoint_external_e2_qualified": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--language", choices=LANGUAGE_ALIASES, required=True)
    parser.add_argument("--gguf-file", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    agent = Qwen35LocalGGUFAgent(args.gguf_file)
    report = asyncio.run(evaluate_qwen35_local_pilot(
        agent, language=args.language, model_variant=args.model,
        gguf_path=args.gguf_file,
        source_repository=args.source_repository,
        source_revision=args.source_revision,
    ))
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True, timeout=10,
    ).stdout.strip()
    report["hardware"] = platform.platform()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False,
    ) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "language": report["language"],
        "model_id": report["model_id"], "gguf_sha256": report["gguf_sha256"],
        "outcomes": [
            {"arm": row["condition"], "success": row["full_task_complete"],
             "total_model_tokens": row["total_model_tokens"],
             "actual_source_calls": row["actual_source_calls"]}
            for row in report["outcomes"]
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

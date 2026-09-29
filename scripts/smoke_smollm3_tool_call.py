"""Pre-B2 SmolLM3 native XML tool-calling smoke.

This script consumes no frozen benchmark row.  It validates the exact model revision,
runtime surface, deterministic first call, and an observation-dependent second call.
"""

from __future__ import annotations

import json
import platform
import re
import resource
import time
from typing import Any

MODEL_NAME = "HuggingFaceTB/SmolLM3-3B"
MODEL_REVISION = "a07cc9a04f16550a088caea529712d1d335b0ac1"
MAX_NEW_TOKENS = 256
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
Issue at most one tool call per assistant turn.
Wait for the tool observation before issuing any later dependent call.
When the required capability is not available among the provided tools,
respond with exactly REQUEST_MORE_TOOLS.
Do not claim completion before the requested task is actually complete.
Destructive tools are subject to executor policy and cannot bypass approval.
"""

TOOLS = [
    {
        "name": "lookup_sample",
        "description": "Resolve a sample name to its registered sample identifier.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Human-readable sample name.",
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_measurement",
        "description": (
            "Read tensile strength for a registered sample identifier. "
            "The sample identifier must come from lookup_sample."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sample_id": {
                    "type": "string",
                    "description": "Registered sample identifier.",
                }
            },
            "required": ["sample_id"],
            "additionalProperties": False,
        },
    },
]


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
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


def runtime_identity() -> dict[str, str]:
    import safetensors
    import tokenizers
    import torch
    import transformers

    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "tokenizers": tokenizers.__version__,
        "safetensors": safetensors.__version__,
    }


def max_rss_mb() -> float:
    # Linux ru_maxrss is KiB.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> None:
    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        StoppingCriteria,
        StoppingCriteriaList,
    )

    torch.manual_seed(SEED)
    torch.set_num_threads(THREADS)

    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        torch_dtype=torch.bfloat16,
        device_map=None,
        attn_implementation="eager",
    )
    model.eval()
    load_seconds = time.perf_counter() - load_started
    context_limit = int(
        getattr(model.config, "max_position_embeddings", 32768)
    )

    stop_ids = tokenizer(
        "</tool_call>",
        add_special_tokens=False,
    )["input_ids"]

    class StopAfterCompleteToolCall(StoppingCriteria):
        def __call__(
            self,
            input_ids: Any,
            scores: Any,
            **kwargs: Any,
        ) -> bool:
            del scores, kwargs
            if not stop_ids or input_ids.shape[-1] < len(stop_ids):
                return False
            return input_ids[0, -len(stop_ids) :].tolist() == stop_ids

    stopping_criteria = StoppingCriteriaList([StopAfterCompleteToolCall()])

    def generate(messages: list[dict[str, str]]) -> dict[str, Any]:
        encoded = tokenizer.apply_chat_template(
            messages,
            xml_tools=TOOLS,
            enable_thinking=False,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"]
        input_tokens = int(input_ids.shape[-1])
        if input_tokens + MAX_NEW_TOKENS > context_limit:
            raise RuntimeError(
                f"smoke context overflow: {input_tokens}+{MAX_NEW_TOKENS}"
                f" > {context_limit}"
            )

        started = time.perf_counter()
        with torch.no_grad():
            output = model.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=MAX_NEW_TOKENS,
                pad_token_id=tokenizer.eos_token_id,
                stopping_criteria=stopping_criteria,
            )
        generation_seconds = time.perf_counter() - started
        generated = output[0, input_ids.shape[-1] :]
        text = tokenizer.decode(
            generated,
            skip_special_tokens=False,
        )
        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": int(generated.shape[-1]),
            "generation_seconds": generation_seconds,
        }

    first_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "For sample alpha-7, first call lookup_sample only. "
                "Wait for its observation before calling read_measurement."
            ),
        },
    ]

    first_a = generate(first_messages)
    first_b = generate(first_messages)
    first_calls_a = parse_tool_calls(first_a["text"])
    first_calls_b = parse_tool_calls(first_b["text"])

    if first_calls_a != first_calls_b:
        raise SystemExit(
            "SmolLM3 smoke is not deterministic under the frozen greedy setup"
        )
    if len(first_calls_a) != 1:
        raise SystemExit(
            f"expected exactly one first-turn tool call, got {first_calls_a!r}"
        )
    first_call = first_calls_a[0]
    if first_call["name"] != "lookup_sample":
        raise SystemExit(f"unexpected first tool: {first_call!r}")
    if first_call["arguments"].get("name") != "alpha-7":
        raise SystemExit(f"unexpected lookup arguments: {first_call!r}")

    observation = {
        "status": "ok",
        "sample_id": "SAMPLE-OBSERVED-73",
    }
    second_messages = [
        *first_messages,
        {"role": "assistant", "content": first_a["text"]},
        {
            "role": "tool",
            "content": (
                "<tool_response>\n"
                + json.dumps(observation, sort_keys=True)
                + "\n</tool_response>"
            ),
        },
    ]
    second = generate(second_messages)
    second_calls = parse_tool_calls(second["text"])
    if len(second_calls) != 1:
        raise SystemExit(
            f"expected exactly one dependent second call, got {second_calls!r}"
        )
    second_call = second_calls[0]
    if second_call["name"] != "read_measurement":
        raise SystemExit(f"unexpected second tool: {second_call!r}")
    if second_call["arguments"].get("sample_id") != "SAMPLE-OBSERVED-73":
        raise SystemExit(
            "second call did not use the observed sample_id: "
            f"{second_call!r}"
        )

    print(
        json.dumps(
            {
                "status": "pass",
                "model": MODEL_NAME,
                "revision": MODEL_REVISION,
                "dtype": "bfloat16",
                "threads": THREADS,
                "context_limit": context_limit,
                "runtime": runtime_identity(),
                "model_load_seconds": load_seconds,
                "max_rss_mb": max_rss_mb(),
                "first_generation_seconds": first_a["generation_seconds"],
                "repeat_generation_seconds": first_b["generation_seconds"],
                "second_generation_seconds": second["generation_seconds"],
                "first_input_tokens": first_a["input_tokens"],
                "first_output_tokens": first_a["output_tokens"],
                "repeat_output_tokens": first_b["output_tokens"],
                "second_input_tokens": second["input_tokens"],
                "second_output_tokens": second["output_tokens"],
                "tool_call_stop_token_count": len(stop_ids),
                "first_call": first_call,
                "second_call": second_call,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

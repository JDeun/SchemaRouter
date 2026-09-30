"""Frozen small-agent runtime for the #506 development screen.

This is the B1 (#420) agent, restored verbatim from the canonical B1 source
revision `b9eadefd3cd076f026a54bbc55a949f0424f5dab`, where it lived in
`scripts/evaluate_agent_utility_phase_b_qwen.py` before the downstream conveyor
moved to SmolLM3. Reusing the exact frozen runtime keeps the development screen
comparable with published B1 context measurements instead of introducing a
fourth uncharacterised model.

The development screen produces development evidence only. Under
`docs/research/governance.md` it may inform design, and it may never be reported
as confirmation.
"""
from __future__ import annotations

import platform
import time
from typing import Any

MODEL_NAME = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
MAX_NEW_TOKENS = 256
MAX_TURNS = 6
SEED = 20260929
THREADS = 4


def runtime_identity() -> dict[str, str]:
    import torch
    import transformers

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }


def _as_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-wrap the harness's flat tool dicts into the Qwen chat-template form.

    The shared harness serializes tools for SmolLM3's `xml_tools=` channel, which
    takes a flat `{name, description, parameters}` object. Qwen's template takes
    the OpenAI `{"type": "function", "function": {...}}` envelope. The inner
    payload is byte-identical in both, so wrapping here reproduces exactly what
    B1 sent rather than approximating it.
    """
    wrapped: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") == "function" and "function" in tool:
            wrapped.append(tool)
        else:
            wrapped.append({"type": "function", "function": tool})
    return wrapped


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
            tools=_as_openai_tools(tools),
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
        text = self.tokenizer.decode(generated, skip_special_tokens=False)
        return {
            "text": text,
            "input_tokens": input_tokens,
            "tool_tokens": tool_tokens,
            "output_tokens": int(generated.shape[-1]),
            "latency_ms": elapsed_ms,
            "context_overflow": False,
        }

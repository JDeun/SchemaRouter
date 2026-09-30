"""Evaluate one frozen #510 runtime-qualification shard."""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_generated_common import (  # noqa: E402
    FINAL_SYSTEM_PROMPT,
    build_extended_registry,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import _as_openai_tools  # noqa: E402
from scripts.evaluate_agent_utility_v4_final_answer import score_envelope  # noqa: E402
from scripts.generate_agent_utility_v8_qualification_corpus import (  # noqa: E402
    QUALIFICATION_CANDIDATE_CONDITION,
    QUALIFICATION_CATALOG_SIZE,
    QUALIFICATION_EVIDENCE_CLASS,
    QUALIFICATION_OBSERVATION_CONDITION,
    QUALIFICATION_SURFACE,
)
from scripts.qualify_agent_utility_runtime import (  # noqa: E402
    ROSTER,
    ROSTER_REVISIONS,
)
from scripts.validate_agent_utility_v8_qualification_corpus import (  # noqa: E402
    validate_qualification_corpus,
)

MAX_NEW_TOKENS = 256
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


class LocalQwenQualificationAgent:
    """Pinned Qwen3 runtime using the same tool-template semantics as B1."""

    def __init__(self, model_name: str, revision: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        self.torch = torch
        self.model_name = model_name
        self.revision = revision
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            revision=revision,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
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
        return prompt, input_tokens, max(0, input_tokens - int(plain_ids.shape[-1]))

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
        return {
            "text": self.tokenizer.decode(generated, skip_special_tokens=False),
            "input_tokens": input_tokens,
            "tool_tokens": tool_tokens,
            "output_tokens": int(generated.shape[-1]),
            "latency_ms": elapsed_ms,
            "context_overflow": False,
        }


def build_agent(candidate: str) -> tuple[Any, dict[str, Any]]:
    if candidate not in ROSTER:
        raise ValueError(f"candidate is not on frozen roster: {candidate!r}")
    revision = ROSTER_REVISIONS[candidate]
    if candidate == "HuggingFaceTB/SmolLM3-3B":
        from scripts.evaluate_agent_utility_phase_b_smollm3 import (
            ATTN_IMPLEMENTATION,
            LocalSmolLM3Agent,
        )

        if ATTN_IMPLEMENTATION != "sdpa":
            raise ValueError("SmolLM3 qualification requires B2_ATTN_IMPLEMENTATION=sdpa")
        agent = LocalSmolLM3Agent()
        detail = {"tool_template": "xml_tools", "attention_implementation": "sdpa"}
    else:
        agent = LocalQwenQualificationAgent(candidate, revision)
        detail = {"tool_template": "openai_function_tools", "attention_implementation": None}

    return agent, {
        "candidate_model": candidate,
        "model_revision": revision,
        "dtype": "bfloat16",
        "device": "cpu",
        "max_new_tokens": MAX_NEW_TOKENS,
        "seed": SEED,
        "threads": THREADS,
        **detail,
        "platform": runtime_identity(),
    }


def evaluate(
    corpus: dict[str, Any],
    *,
    candidate: str,
    task_ids: set[str],
) -> dict[str, Any]:
    validate_qualification_corpus(corpus)
    if corpus["catalog_sizes"] != [QUALIFICATION_CATALOG_SIZE]:
        raise ValueError("qualification catalog size drifted")

    tasks = [
        task
        for task in corpus["tasks"]
        if str(task["semantic_task_id"]) in task_ids
    ]
    if {str(task["semantic_task_id"]) for task in tasks} != task_ids:
        raise ValueError("requested qualification task IDs are not all present")

    started = time.perf_counter_ns()
    agent, identity = build_agent(candidate)
    model_load_ms = (time.perf_counter_ns() - started) / 1_000_000
    registry = build_extended_registry(QUALIFICATION_CATALOG_SIZE)

    rows: list[dict[str, Any]] = []
    for task in tasks:
        row = run_generated_episode(
            agent,
            registry,
            task,
            QUALIFICATION_OBSERVATION_CONDITION,
            system_prompt=FINAL_SYSTEM_PROMPT,
            candidate_condition=QUALIFICATION_CANDIDATE_CONDITION,
            observation_transform=None,
        )
        row["catalog_size"] = QUALIFICATION_CATALOG_SIZE
        row["projection_stratum"] = str(task["projection_stratum"])
        row.update(score_envelope(task, str(row["final_text"])))
        rows.append(row)
        print(
            json.dumps(
                {
                    "candidate": candidate,
                    "task_id": row["semantic_task_id"],
                    "final_envelope_valid": row["final_envelope_valid"],
                    "tool_call_count": row["tool_call_count"],
                    "required_fact_recall": row["required_fact_recall"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    return {
        "schema_version": 1,
        "issue": 510,
        "experiment": corpus["experiment"],
        "evidence_class": QUALIFICATION_EVIDENCE_CLASS,
        "surface": QUALIFICATION_SURFACE,
        "source_revision": corpus["source_revision"],
        "harness_revision": corpus["source_revision"],
        "corpus_tasks_sha256": corpus["tasks_sha256"],
        "candidate_model": candidate,
        "model_revision": ROSTER_REVISIONS[candidate],
        "runtime": identity,
        "model_load_ms": model_load_ms,
        "task_ids": sorted(task_ids),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--candidate", required=True, choices=ROSTER)
    parser.add_argument("--task-ids", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    task_ids = {value.strip() for value in args.task_ids.split(",") if value.strip()}
    result = evaluate(corpus, candidate=args.candidate, task_ids=task_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

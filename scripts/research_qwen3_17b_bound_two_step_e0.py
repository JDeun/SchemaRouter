"""Pinned larger Qwen3-1.7B versus unchanged 0.6B native-host E0 negative.

Separate model-identity experiment. The existing user prompts, two public
native package bound provider operations, model turn budget, strict tool
parser and final-answer grader are imported UNMODIFIED from #1506.
No prompt modifications, extra attempts, different source exposure or
independent E2 model promotion can be inferred from these published tasks.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from scripts.agent_utility_v7_dev_agent import (
    MAX_NEW_TOKENS,
    MAX_TURNS,
    MODEL_NAME as SMALL_MODEL,
    MODEL_REVISION as SMALL_REVISION,
    SEED,
    THREADS,
    LocalQwenAgent,
    runtime_identity,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    LANGUAGES,
    ROOT,
    run_model_selected_bound_two_step_e0,
)

MODEL_NAME = "Qwen/Qwen3-1.7B"
# An unchanging Hub commit, not a moving tag; require the full server SHA to
# start with the source-proven published commit prefix before downloading.
REVISION_PIN = "70d244c"
LICENSE = "apache-2.0"


def checked_commit_hash(raw: str) -> str:
    if (
        type(raw) is not str
        or len(raw) != 40
        or not all(c in "0123456789abcdef" for c in raw)
        or not raw.startswith(REVISION_PIN)
    ):
        raise ValueError("unverified Qwen3-1.7B source revision")
    return raw


class LocalQwen17BDevAgent(LocalQwenAgent):
    """Same frozen Qwen3 tokenizer and generate protocol, new exact weights."""

    def __init__(self) -> None:
        import torch
        from huggingface_hub import model_info
        from transformers import AutoModelForCausalLM, AutoTokenizer

        resolved = checked_commit_hash(
            model_info(MODEL_NAME, revision=REVISION_PIN).sha,
        )
        self.resolved_revision = resolved
        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, revision=resolved, trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME, revision=resolved, trust_remote_code=False,
            torch_dtype=torch.float32, device_map=None,
        )
        self.model.eval()
        self.context_limit = int(
            getattr(self.model.config, "max_position_embeddings", 32768)
        )


def evaluate_candidate_e0(agent: Any, *, revision: str) -> dict[str, Any]:
    """Host-bound task correctness comes exclusively from the parent grader."""
    checked_commit_hash(revision)
    started = time.monotonic()
    episodes = [
        asyncio.run(run_model_selected_bound_two_step_e0(
            agent, language=lang,
        ))
        for lang in LANGUAGES
    ]
    elapsed = time.monotonic() - started
    return {
        "evidence_tier": "UNATTESTED_SIZE_CANDIDATE_E0_TEST_ONLY",
        "candidate_model": MODEL_NAME,
        "candidate_revision": revision,
        "frozen_small_baseline": {
            "model": SMALL_MODEL,
            "revision": SMALL_REVISION,
            "source_run": "https://github.com/JDeun/SchemaRouter/actions/runs/39029981154",
            "observed_full_task_correct": 0,
            "case_count": 3,
        },
        "case_count": len(episodes),
        "per_language": episodes,
        "candidate_generation_elapsed_s": round(elapsed, 3),
        "model_initialization_success": True,
        "real_native_external_provider_execution": False,
        "actual_real_model_inference_measured": False,
        "independent_e2_qualified": False,
        "calibrated_no_fit": False,
        "model_default_promoted": False,
        "release_safety_gate_passed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-cpu"), required=True)
    parser.add_argument(
        "--out", type=Path,
        default=Path("artifacts/qwen3-17b-bound-host-e0/report.json"),
    )
    args = parser.parse_args()
    if args.mode == "validate":
        print(json.dumps({
            "candidate": MODEL_NAME,
            "revision_prefix": REVISION_PIN,
            "candidate_license": LICENSE,
            "baseline": SMALL_MODEL,
            "same_max_turns": MAX_TURNS,
            "same_generation_budget": MAX_NEW_TOKENS,
            "runner": "GitHub Actions ubuntu-24.04 4 vCPU 16 GB public repository",
            "independent_e2_qualified": False,
            "actual_real_model_inference_measured": False,
        }))
        return

    started = time.monotonic()
    agent = LocalQwen17BDevAgent()
    report = evaluate_candidate_e0(agent, revision=agent.resolved_revision)
    report.update({
        "evidence_tier": "REAL_QWEN3_17B_CPU_BOUND_HOST_E0_DEV_ONLY",
        "model_load_and_generation_elapsed_s": round(
            time.monotonic() - started, 3,
        ),
        "peak_process_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cpu_runtime": {"device": "cpu", **runtime_identity()},
        "hardware": platform.platform(),
        "source_revision": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip(),
        "actual_real_model_inference_measured": True,
        "per_language": [{
            **item,
            "evidence_tier": "REAL_QWEN3_17B_CPU_BOUND_HOST_E0_DEV_ONLY",
            "actual_model_inference_measured": True,
        } for item in report["per_language"]],
        "limitations": [
            "three disclosed researcher-authored EN/KO/JA prompts, no independent cases",
            "synthetic in-process bound read providers, no external native provider",
            "small baseline was a prior source run, not same-head paired inference",
            "not a calibrated no-fit test and not proof of commercial suitability",
        ],
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "model": report["candidate_model"],
        "sha": report["candidate_revision"],
        "model_seconds": report["model_load_and_generation_elapsed_s"],
        "peak_rss_kib": report["peak_process_rss_kib_linux"],
        "by_language": {
            r["language"]: {
                k: r[k] for k in (
                    "actual_bound_host_calls", "full_task_correct",
                    "termination_reason", "malformed_model_turn",
                )
            } for r in report["per_language"]
        },
        "independent_e2_qualified": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

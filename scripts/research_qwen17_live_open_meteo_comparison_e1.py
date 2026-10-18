"""Pinned larger local Qwen3-1.7B on existing real-provider 2-hop E1 DEV.

Uses IDENTICAL #1522 model-generated calls, host-owned authorization,
Open-Meteo sources, task and final oracle. Only checkpoint/tokenizer differ.
Three pre-exposed, researcher-authored examples; not independent E2.
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

import httpx

from scripts.agent_utility_v7_dev_agent import (
    SEED,
    THREADS,
    LocalQwenAgent,
    runtime_identity,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    MODEL_NAME as BASELINE_MODEL,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    MODEL_REVISION as BASELINE_REVISION,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    ROOT,
    evaluate,
)

MODEL_ID = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
BASELINE_REAL_RUN = "https://github.com/JDeun/SchemaRouter/actions/runs/39089681858"


class LocalQwen17BRealAgent(LocalQwenAgent):
    """Reuse the *exact* old generation algorithm with model weights swapped."""

    def __init__(self) -> None:
        import torch
        from huggingface_hub import model_info
        from transformers import AutoModelForCausalLM, AutoTokenizer

        source = model_info(MODEL_ID, revision=REVISION).sha
        if (
            type(source) is not str or source != REVISION
            or len(source) != 40
            or not all(c in "0123456789abcdef" for c in source)
        ):
            raise ValueError("candidate checkpoint SHA not independently resolved")
        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID, revision=source, trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, revision=source, trust_remote_code=False,
            torch_dtype=torch.float32, device_map=None,
        )
        self.model.eval()
        self.context_limit = int(
            getattr(self.model.config, "max_position_embeddings", 32768)
        )


async def compare_model(
    agent: Any, client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Reuse #1522 unchanged, keeping model source identity and outcome tiers."""
    started = time.perf_counter()
    report = await evaluate(agent, client)
    if (
        report.get("case_count") != 3
        or report.get("total_real_source_calls") != sum(
            r["real_geocoding_calls"] + r["real_forecast_calls"]
            for r in report["outcomes"]
        )
    ):
        raise ValueError("unchanged real provider oracle denominator drift")
    report.update({
        "study": "REAL_QWEN17_NATIVE_OPEN_METEO_TWO_STEP_E1_DEV",
        "model_id": MODEL_ID,
        "model_revision": REVISION,
        "candidate_only_checkpoint_changed": True,
        "baseline": {
            "study": "REAL_QWEN_NATIVE_OPEN_METEO_TWO_STEP_E1_DEV",
            "model_id": BASELINE_MODEL,
            "model_revision": BASELINE_REVISION,
            "baseline_run": BASELINE_REAL_RUN,
            "baseline_full_task_successes": 1,
            "baseline_case_count": 3,
        },
        "candidate_provider_and_model_seconds": round(
            time.perf_counter() - started, 3,
        ),
        "actual_pinned_model_inference": True,
        "real_provider_observed": True,
        "private_holdout": False,
        "independent_e2_qualified": False,
        "released_or_promoted": False,
        "single_run_dynamic_source": True,
        "limitations": [
            "three already publicly exposed developer-authored requests",
            "baseline source time/weather may differ across actual runs",
            "not joint paired same-run model evaluation",
            "not a benchmark for unsupported or unauthorized requests",
            "no source-original independent task author or bilingual language oracle",
        ],
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    agent = LocalQwen17BRealAgent()

    async def _run() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), follow_redirects=False,
        ) as client:
            return await compare_model(agent, client)

    report = asyncio.run(_run())
    report["candidate_model_load_and_run_seconds"] = round(
        time.perf_counter() - start, 3,
    )
    report["peak_process_rss_kib_linux"] = resource.getrusage(
        resource.RUSAGE_SELF,
    ).ru_maxrss
    report["environment"] = {"device": "cpu", **runtime_identity()}
    report["platform"] = platform.platform()
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, timeout=10, check=True,
    ).stdout.strip()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "model_revision": report["model_revision"],
        "complete_tasks": report["model_generated_full_task_successes"],
        "real_provider_calls": report["total_real_source_calls"],
        "by_language": {
            r["language"]: {
                "source_calls": r["real_geocoding_calls"]
                + r["real_forecast_calls"],
                "full_task_complete": r["full_task_complete"],
                "stop": r["termination_reason"],
            }
            for r in report["outcomes"]
        },
        "independent_e2_qualified": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Real Qwen3 / original live Open-Meteo paired source-progress E1 research.

NO host-executed next step or model-generated result substitution. The
progress notice is only an accurate host statement after a validated
source observation. Published original E1 tasks, not independent E2.
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

import httpx

from scripts.agent_utility_v7_dev_agent import LocalQwenAgent, runtime_identity
from scripts.research_qwen_state_ready_open_meteo_e1 import ROOT, compare

EVIDENCE = "REAL_QWEN_OPEN_METEO_GROUNDED_PROGRESS_E1_EXPOSED_DEV_NOT_E2"
ARMS = ("state_ready", "state_ready_progress")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--transport-retry-budget", type=int, default=1)
    args = parser.parse_args()
    if type(args.transport_retry_budget) is not int or args.transport_retry_budget != 1:
        raise ValueError("paired progress E1 uses the same single idempotent retry")
    start = time.perf_counter()
    agent = LocalQwenAgent()

    async def run() -> dict:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), follow_redirects=False,
        ) as client:
            return await compare(
                agent, client, transport_retry_budget=1,
                arms=ARMS, evidence=EVIDENCE,
            )

    report = asyncio.run(run())
    report["elapsed_model_load_and_run_seconds"] = round(
        time.perf_counter() - start, 2,
    )
    report["peak_process_rss_kib_linux"] = resource.getrusage(
        resource.RUSAGE_SELF,
    ).ru_maxrss
    report["platform"] = platform.platform()
    report["runtime_identity"] = runtime_identity()
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "by_arm": report["by_arm"],
        "independent_e2_qualified": False,
        "released": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

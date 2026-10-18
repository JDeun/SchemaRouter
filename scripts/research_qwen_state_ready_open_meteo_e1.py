"""Actual pinned Qwen3 + real Open-Meteo: paired state-ready native menus E1.

Only the source-visible tool menu changes. The exact original model runtime,
native provider, strict post-hoc factual oracle and original source tasks are
unchanged. Source failures are not rescued. This is exposed E1 DEV, not E2.
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
    MODEL_NAME,
    MODEL_REVISION,
    LocalQwenAgent,
    runtime_identity,
)
from scripts.research_open_meteo_live_two_hop_e1 import CASES
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    ROOT,
    evaluate_one,
)

ARMS = ("all_visible", "state_ready")
EVIDENCE = "REAL_QWEN_OPEN_METEO_SOURCE_READY_E1_EXPOSED_DEV_NOT_E2"


async def compare(agent: Any, client: httpx.AsyncClient) -> dict[str, Any]:
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("actual model generator required")
    outcomes: dict[str, dict[str, dict[str, Any]]] = {
        arm: {} for arm in ARMS
    }
    started = time.perf_counter()
    # Alternate order for the same previous original E1 source tasks.
    # Provider time/current data are re-observed independently per arm.
    for i, (language, city, country) in enumerate(CASES):
        ordered = ARMS if i % 2 == 0 else tuple(reversed(ARMS))
        for arm in ordered:
            row = await evaluate_one(
                agent, client, language=language, city=city, country=country,
                menu_mode=arm,
            )
            if row["language"] != language or row["independent_e2_qualified"]:
                raise ValueError("corrupt native source task outcome")
            if row["full_task_complete"] and not (
                row["strict_final_answer_correct"]
                and row["model_generated_two_step_complete"]
                and row["real_geocoding_calls"] == 1
                and row["real_forecast_calls"] == 1
            ):
                raise ValueError("unsupported real task completion claim")
            outcomes[arm][language] = row
    by_arm: dict[str, dict[str, Any]] = {}
    for arm, cases in outcomes.items():
        by_arm[arm] = {
            "completed_strict_real_provider_tasks": sum(
                x["full_task_complete"] for x in cases.values()
            ),
            "source_validated_calls": sum(
                x["real_geocoding_calls"] + x["real_forecast_calls"]
                for x in cases.values()
            ),
            "http_attempts": sum(
                x["real_geocoding_http_attempts"] + x["real_forecast_http_attempts"]
                for x in cases.values()
            ),
            "by_language": {
                language: {
                    "strict_complete": x["full_task_complete"],
                    "strict_final_answer_correct": x["strict_final_answer_correct"],
                    "validated_geocodes": x["real_geocoding_calls"],
                    "validated_forecasts": x["real_forecast_calls"],
                    "http_attempts": (
                        x["real_geocoding_http_attempts"]
                        + x["real_forecast_http_attempts"]
                    ),
                    "termination_reason": x["termination_reason"],
                    "trusted_failure_stage": x["trusted_failure_stage"],
                    "model_turns": x["model_turns"],
                    "generation_ms": x["model_generation_ms"],
                }
                for language, x in cases.items()
            },
        }
    return {
        "study": EVIDENCE,
        "arms": list(ARMS),
        "case_count_per_arm": len(CASES),
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "original_live_provider_attempts": True,
        "real_pinned_model_inference": True,
        "host_derived_state_ready_menu_only_in_candidate": True,
        "same_original_source_case_contract": True,
        "independent_e2_qualified": False,
        "default_product_modified": False,
        "release_qualified": False,
        "by_arm": by_arm,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "limitations": [
            "Three previously disclosed source-author tasks, not independent E2",
            "Alternating-order paired arms, but live provider state can drift",
            "Ready menus reduce tool choice; cannot establish autonomous ranking",
            "Missing native provider consent and private EN/KO/JA source gold",
            "No unsupported/OOD specificity, BFCL safe refusal or recall validation",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    agent = LocalQwenAgent()

    async def run() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), follow_redirects=False,
        ) as client:
            return await compare(agent, client)

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
        "model_revision": report["model_revision"],
        "by_arm": report["by_arm"],
        "independent_e2_qualified": False,
        "released": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

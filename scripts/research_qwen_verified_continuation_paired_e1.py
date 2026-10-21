"""Paired actual-Qwen/Open-Meteo source study of ONE bounded early-final reminder.

This experiment reuses the original verified native E1 evaluator, source host,
Qwen weights and strict factual scorer. It is disclosed DEV, never independent E2.
No product router, source executor, or default agent behavior is modified.
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
from scripts.research_real_qwen_open_meteo_two_hop_e1 import ROOT, evaluate_one

STUDY = "REAL_QWEN_VERIFIED_CONTINUATION_PAIRED_E1_EXPOSED_DEV_NOT_E2"
ARMS = ("original", "one_verified_reminder")
MODEL_TOKEN_KEYS = ("input_tokens", "tool_tokens", "output_tokens")
MAX_HTTP_PER_EPISODE = 4  # two native GETs with at most one transport retry each


class MeteredAgent:
    """Account only returned model token counts; never record prompts or outputs."""

    def __init__(self, agent: Any) -> None:
        if not callable(getattr(agent, "generate", None)):
            raise ValueError("model generation required")
        self.agent = agent
        self.calls = 0
        self.totals = {key: 0 for key in MODEL_TOKEN_KEYS}

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = self.agent.generate(messages, tools)
        if type(result) is not dict:
            raise ValueError("invalid model generation result")
        # Missing/non-integer usage cannot be silently converted into zero cost.
        for key in MODEL_TOKEN_KEYS:
            value = result.get(key)
            if type(value) is not int or value < 0:
                raise ValueError("unavailable trustworthy model token accounting")
        if result["tool_tokens"] > result["input_tokens"]:
            raise ValueError("tool tokens exceed model input tokens")
        self.calls += 1
        for key in MODEL_TOKEN_KEYS:
            self.totals[key] += result[key]
        return result


def _checked_public_row(
    row: dict[str, Any], meter: MeteredAgent, wall_ms: float, *,
    language: str, arm: str,
) -> dict[str, Any]:
    if row["language"] != language or row["independent_e2_qualified"] is not False:
        raise ValueError("unqualified or mismatched model/source outcome")
    if row["model_turns"] != meter.calls or not 1 <= meter.calls <= 4:
        raise ValueError("model-turn accounting mismatch")
    if row["full_task_complete"] and not (
        row["model_generated_two_step_complete"]
        and row["strict_final_answer_correct"]
        and row["real_geocoding_calls"] == 1
        and row["real_forecast_calls"] == 1
    ):
        raise ValueError("unverified strict weather completion")
    attempts = row["real_geocoding_http_attempts"] + row["real_forecast_http_attempts"]
    if not 0 <= attempts <= MAX_HTTP_PER_EPISODE:
        raise ValueError("unbounded external source requests")
    if arm == "original":
        if "host_evidence_reprompts" in row:
            raise ValueError("original control arm changed")
        reminders = 0
    else:
        reminders = row["host_evidence_reprompts"]
        if type(reminders) is not int or reminders not in (0, 1):
            raise ValueError("invalid bounded reminder evidence")
    return {
        "language": language,
        "strict_full_task_pass": row["full_task_complete"],
        "verified_geocodes": row["real_geocoding_calls"],
        "verified_weather": row["real_forecast_calls"],
        "http_attempts": attempts,
        "model_turns": meter.calls,
        "host_evidence_reprompts": reminders,
        "termination_reason": row["termination_reason"],
        "trusted_failure_stage": row["trusted_failure_stage"],
        "trusted_transport_error_kind": row["trusted_transport_error_kind"],
        "final_validation_failure_kind": row["trusted_final_validation_failure_kind"],
        "model_generation_ms": row["model_generation_ms"],
        "episode_wall_ms": round(wall_ms, 1),
        **meter.totals,
    }


async def compare(
    agent: Any, client: httpx.AsyncClient, *, transport_retry_budget: int = 1,
) -> dict[str, Any]:
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("pinned generator required")
    if type(transport_retry_budget) is not int or transport_retry_budget != 1:
        raise ValueError("fixed preregistered retry budget of one required")
    by_arm: dict[str, dict[str, dict[str, Any]]] = {arm: {} for arm in ARMS}
    started = time.perf_counter()

    for case_number, (language, city, country) in enumerate(CASES):
        order = ARMS if case_number % 2 == 0 else tuple(reversed(ARMS))
        for arm in order:
            meter = MeteredAgent(agent)
            episode_started = time.perf_counter()
            row = await evaluate_one(
                meter, client, language=language, city=city, country=country,
                menu_mode="state_ready",
                transport_retry_budget=transport_retry_budget,
                evidence_reprompt_budget=int(arm == "one_verified_reminder"),
            )
            by_arm[arm][language] = _checked_public_row(
                row, meter, (time.perf_counter() - episode_started) * 1000,
                language=language, arm=arm,
            )

    return {
        "study": STUDY,
        "arms": list(ARMS),
        "paired_case_count": len(CASES),
        "study_design": "alternating-order, fixed original state-ready menu",
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "shared_provider": "original Open-Meteo geocoding and weather HTTPS",
        "transport_retry_budget": transport_retry_budget,
        "model_inference_expected": True,
        "source_is_live_not_frozen": True,
        "provider_observations_not_shared_between_arms": True,
        "independent_e2_qualified": False,
        "product_default_changed": False,
        "release_qualified": False,
        "by_arm": {
            arm: {
                "strict_full_task_passes": sum(
                    bool(row["strict_full_task_pass"]) for row in cases.values()
                ),
                "http_attempts": sum(
                    row["http_attempts"] for row in cases.values()
                ),
                "model_turns": sum(
                    row["model_turns"] for row in cases.values()
                ),
                "model_generation_ms": round(sum(
                    row["model_generation_ms"] for row in cases.values()
                ), 1),
                "host_evidence_reprompts": sum(
                    row["host_evidence_reprompts"] for row in cases.values()
                ),
                "token_totals": {
                    key: sum(row[key] for row in cases.values())
                    for key in MODEL_TOKEN_KEYS
                },
                "by_language": cases,
            }
            for arm, cases in by_arm.items()
        },
        "duration_seconds": round(time.perf_counter() - started, 2),
        "limitations": [
            "Only three previously disclosed author-written EN/KO/JA tasks",
            "One pinned local model; no independent author, blind E2 or confidence interval",
            "Live provider time and transport may differ across paired episodes",
            "No no-fit, OOD, provider approval or general routing benchmark",
            "Any observed improvement is E1 hypothesis evidence, never release proof",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    agent = LocalQwenAgent()

    async def run() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), follow_redirects=False,
        ) as client:
            return await compare(agent, client)

    report = asyncio.run(run())
    report["actual_pinned_model_inference"] = True
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout.strip()
    report["hardware"] = platform.platform()
    report["runtime_identity"] = runtime_identity()
    report["peak_process_rss_kib_linux"] = resource.getrusage(
        resource.RUSAGE_SELF,
    ).ru_maxrss
    report["elapsed_load_and_study_seconds"] = round(
        time.perf_counter() - started, 2,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": STUDY,
        "strict_passes": {
            arm: data["strict_full_task_passes"]
            for arm, data in report["by_arm"].items()
        },
        "independent_e2_qualified": False,
    }))


if __name__ == "__main__":
    main()

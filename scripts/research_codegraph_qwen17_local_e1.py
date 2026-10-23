"""Genuine pinned Qwen3-1.7B in the separate, K5-safe four-route local E1.

Do NOT treat a different checkpoint as evidence that context selection alone
improves task quality. Reuse exactly the original registered local source,
four arms, source execution authority and scorer. No remote provider HTTP,
private held-out E2, or default product change.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import subprocess
from pathlib import Path

from scripts.agent_utility_v7_dev_agent import MODEL_NAME as BASELINE_MODEL_ID
from scripts.agent_utility_v7_dev_agent import MODEL_REVISION as BASELINE_REVISION
from scripts.research_codegraph_local_multiroute_e1 import (
    LANGUAGE_ALIASES,
    ROOT,
    run_local_multiroute_codegraph_e1,
)
from scripts.research_qwen17_live_open_meteo_comparison_e1 import (
    MODEL_ID,
    REVISION,
    LocalQwen17BRealAgent,
)


async def evaluate_candidate(
    agent: LocalQwen17BRealAgent, *, language: str,
) -> dict:
    """Run one local synthetic task under genuine four-arm K5 constraints."""
    if type(agent) is not LocalQwen17BRealAgent:
        raise TypeError("pinned Qwen3-1.7B instance required for source receipts")
    report = await run_local_multiroute_codegraph_e1(
        agent, language=language, condition="joined", catalog_size=4,
    )
    if (
        report["status"] != "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2"
        or report["source_route_count"] != 4
        or len(report["outcomes"]) != 4
    ):
        raise ValueError("pinned candidate study lacks comparable K5 local source")
    return {
        **report,
        "study": "CODEGRAPH_QWEN17_LOCAL_FOUR_ARM_E1_DEV",
        "model_id": MODEL_ID,
        "model_revision": REVISION,
        "actual_pinned_model_inference": True,
        "checkpoint_only_model_intervention": True,
        "baseline_model_id": BASELINE_MODEL_ID,
        "baseline_model_revision": BASELINE_REVISION,
        "real_external_provider_observed": False,
        "local_control_only": True,
        "independent_e2_qualified": False,
        "release_qualified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=("four-route",), required=True)
    parser.add_argument("--language", choices=LANGUAGE_ALIASES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # This class validates its independently pinned 40-character Hugging Face
    # source SHA before loading and shares exactly the legacy generation API.
    agent = LocalQwen17BRealAgent()
    report = asyncio.run(evaluate_candidate(agent, language=args.language))
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
        "study": report["study"],
        "status": report["status"],
        "language": report["language"],
        "qualified_task_denominator": report["qualified_task_denominator"],
        "actual_source_calls": report["source_call_count"],
        "model_turns": {
            row["condition"]: row["model_turns"] for row in report["outcomes"]
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()

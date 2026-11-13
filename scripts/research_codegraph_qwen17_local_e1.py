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
    diagnose_model_actions: bool = False,
    experimental_bare_native_json: bool = False,
    experimental_single_step_prompt: bool = False,
    experimental_g5_verified_continuation: bool = False,
    experimental_bare_schema_request: bool = False,
    experimental_graph_path_order_prompt: bool = False,
    experimental_graph_frontier: bool = False,
    experimental_strict_unwrapped_json: bool = False,
) -> dict:
    """Run one local synthetic task under genuine four-arm K5 constraints."""
    if type(agent) is not LocalQwen17BRealAgent:
        raise TypeError("pinned Qwen3-1.7B instance required for source receipts")
    optional = {}
    if diagnose_model_actions:
        optional["diagnose_model_actions"] = True
    if experimental_bare_native_json:
        optional["experimental_bare_native_json"] = True
    if experimental_single_step_prompt:
        optional["experimental_single_step_prompt"] = True
    if experimental_g5_verified_continuation:
        optional["experimental_g5_verified_continuation"] = True
    if experimental_bare_schema_request:
        optional["experimental_bare_schema_request"] = True
    if experimental_graph_path_order_prompt:
        optional["experimental_graph_path_order_prompt"] = True
    if experimental_graph_frontier:
        optional["experimental_graph_frontier"] = True
    if type(experimental_strict_unwrapped_json) is not bool:
        raise ValueError("research strict envelope flag must be boolean")
    if experimental_strict_unwrapped_json:
        optional["experimental_strict_unwrapped_json"] = True
    report = await run_local_multiroute_codegraph_e1(
        agent, language=language, condition="joined", catalog_size=4,
        **optional,
    )
    if (
        report["status"] != (
            "E1_MEASURED_LOCAL_FIVE_ARM_NOT_E2" if experimental_graph_frontier
            else "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2"
        )
        or report["source_route_count"] != 4
        or len(report["outcomes"]) != (5 if experimental_graph_frontier else 4)
    ):
        raise ValueError("pinned candidate study lacks comparable K5 local source")
    return {
        **report,
        "study": (
            "CODEGRAPH_QWEN17_STRICT_JSON_ENVELOPE_E1_DEV"
            if experimental_strict_unwrapped_json
            else "CODEGRAPH_QWEN17_LOCAL_FOUR_ARM_E1_DEV"
        ),
        "strict_unwrapped_json_treatment": experimental_strict_unwrapped_json,
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
    parser.add_argument("--diagnose-model-actions", action="store_true")
    parser.add_argument("--experimental-bare-native-json", action="store_true")
    parser.add_argument("--experimental-single-step-prompt", action="store_true")
    parser.add_argument("--experimental-g5-verified-continuation", action="store_true")
    parser.add_argument("--experimental-bare-schema-request", action="store_true")
    parser.add_argument("--experimental-graph-path-order-prompt", action="store_true")
    parser.add_argument("--experimental-graph-frontier", action="store_true")
    parser.add_argument("--strict-unwrapped-tool-json", action="store_true")
    parser.add_argument("--paired-envelope-comparison", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # This class validates its independently pinned 40-character Hugging Face
    # source SHA before loading and shares exactly the legacy generation API.
    if args.paired_envelope_comparison and (
        args.strict_unwrapped_tool_json or args.diagnose_model_actions
        or args.experimental_bare_native_json or args.experimental_graph_frontier
        or args.experimental_bare_schema_request or args.experimental_single_step_prompt
        or args.experimental_g5_verified_continuation
        or args.experimental_graph_path_order_prompt
    ):
        parser.error("paired strict envelope comparison must be a single isolated treatment")
    agent = LocalQwen17BRealAgent()
    control = None
    if args.paired_envelope_comparison:
        control = asyncio.run(evaluate_candidate(agent, language=args.language))
    report = asyncio.run(evaluate_candidate(
        agent, language=args.language,
        diagnose_model_actions=args.diagnose_model_actions,
        experimental_bare_native_json=args.experimental_bare_native_json,
        experimental_single_step_prompt=args.experimental_single_step_prompt,
        experimental_g5_verified_continuation=args.experimental_g5_verified_continuation,
        experimental_bare_schema_request=args.experimental_bare_schema_request,
        experimental_graph_path_order_prompt=args.experimental_graph_path_order_prompt,
        experimental_graph_frontier=args.experimental_graph_frontier,
        experimental_strict_unwrapped_json=(
            args.strict_unwrapped_tool_json or args.paired_envelope_comparison
        ),
    ))
    if control is not None:
        if control["source_receipt_digest"] != report["source_receipt_digest"]:
            raise ValueError("paired original source drift")
        report = {
            "study": "CODEGRAPH_QWEN17_PAIRED_STRICT_ENVELOPE_E1_DEV",
            "model_id": MODEL_ID, "model_revision": REVISION,
            "language": args.language,
            "source_receipt_digest": control["source_receipt_digest"],
            "strict_k": 5,
            "intervention": "canonical_offered_unwrapped_tool_json_only",
            "independent_e2_qualified": False, "release_qualified": False,
            "results": {"original_strict_control": control,
                        "exact_json_envelope_treatment": report},
        }
    report["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True, timeout=10,
    ).stdout.strip()
    report["hardware"] = platform.platform()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        report, indent=2, sort_keys=True, allow_nan=False,
    ) + "\n", encoding="utf-8")
    if control is not None:
        printed = {
            "study": report["study"],
            "language": report["language"],
            "full_task_counts": {
                arm: sum(row["full_task_complete"] is True
                         for row in experiment["outcomes"])
                for arm, experiment in report["results"].items()
            },
        }
    else:
        printed = {
            "study": report["study"],
            "status": report["status"],
            "language": report["language"],
            "qualified_task_denominator": report["qualified_task_denominator"],
            "actual_source_calls": report["source_call_count"],
            "model_turns": {
                row["condition"]: row["model_turns"] for row in report["outcomes"]
            },
        }
    print(json.dumps(printed, sort_keys=True))


if __name__ == "__main__":
    main()
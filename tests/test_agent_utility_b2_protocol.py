from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_agent_utility_b2_freeze import (  # noqa: E402
    EXPECTED_CATALOG_SHAS,
    EXPECTED_TASK_SHA,
    freeze,
)
from scripts.verify_agent_utility_b2_candidate_sets import (  # noqa: E402
    EXPECTED_ROWS,
    EXPECTED_SHA256,
    verify,
)

PREREG = ROOT / "benchmarks" / "agent-utility-v1-b2-preregistration.json"


def test_b2_preregistration_pins_strong_non_qwen_model() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))

    assert data["issue"] == 423
    assert data["status"] == "frozen_before_any_b2_model_inference"
    assert data["model"]["name"] == "HuggingFaceTB/SmolLM3-3B"
    assert data["model"]["revision"] == (
        "a07cc9a04f16550a088caea529712d1d335b0ac1"
    )
    assert data["model"]["family"] == "SmolLM3"
    assert data["model"]["dtype"] == "bfloat16"
    assert data["model"]["enable_thinking"] is False
    assert data["model"]["do_sample"] is False
    assert data["model_selection_governance"]["non_qwen_family"] is True
    assert data["model_selection_governance"]["selected_from_b1_row_errors"] is False

    assert data["conditions"] == [
        "FULL",
        "SR-5",
        "SR-10",
        "SR-PROGRESSIVE",
        "ORACLE",
    ]
    assert data["expected_episode_count"] == 460
    assert data["tool_interface"]["tokenizer_argument"] == "xml_tools"
    assert data["pre_benchmark_smoke"]["full_b2_inference_authorized_only_after_smoke_pass"] is True



def test_b2_full_inference_authorization_is_bound_to_terminal_smoke() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    smoke = data["pre_benchmark_smoke"]
    stopping = data["model"]["generation_stopping"]

    assert stopping["completed_tool_call_suffix"] == "</tool_call>"
    assert stopping["condition_independent"] is True
    assert stopping["benchmark_row_dependent"] is False

    assert smoke["authorized_smoke_result"] == "pass"
    assert smoke["authorized_smoke_workflow_run"] == 36548416952
    assert smoke["authorized_smoke_source_sha"] == (
        "7391b0a0703c7cabb086421f81b838111abefdc3"
    )
    assert smoke["authorized_smoke_artifact_digest"] == (
        "sha256:7a0e1c93f83a5937a4ea3baaaa088caf"
        "88d5eb0a79229113dbd6a0f7b24243ca"
    )
    assert smoke["full_b2_inference_authorized"] is True
    assert smoke["benchmark_rows_consumed"] is False
    assert smoke["authorized_metrics"]["first_output_tokens"] == 21
    assert smoke["authorized_metrics"]["second_output_tokens"] == 25

def test_b2_freeze_reproduces_canonical_b1_identity(tmp_path: Path) -> None:
    manifest = freeze(tmp_path)

    assert manifest["task_count"] == 23
    assert manifest["single_task_count"] == 17
    assert manifest["multi_task_count"] == 6
    assert manifest["tasks_sha256"] == EXPECTED_TASK_SHA

    for size, expected in EXPECTED_CATALOG_SHAS.items():
        assert manifest["catalogs"][str(size)]["endpoint_count"] == size
        assert manifest["catalogs"][str(size)]["sha256"] == expected


def test_b2_candidate_sets_reproduce_canonical_b1() -> None:
    result = verify()
    assert result == {
        "rows": EXPECTED_ROWS,
        "sha256": EXPECTED_SHA256,
        "status": "pass",
    }

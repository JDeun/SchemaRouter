from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_agent_utility_b2_freeze import (
    EXPECTED_CATALOG_SHAS,
    EXPECTED_TASK_SHA,
    freeze,
)
from scripts.verify_agent_utility_b2_candidate_sets import (
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

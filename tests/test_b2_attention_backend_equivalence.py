from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_b2_attention_backends.py"

spec = importlib.util.spec_from_file_location("b2_compare", SCRIPT)
assert spec is not None and spec.loader is not None
b2_compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b2_compare)


def test_normalization_ignores_timing_and_backend_only() -> None:
    eager = {
        "runtime": {"python": "3.12.14"},
        "model": {
            "attention_implementation": "eager",
            "static_prefix_cache": False,
            "name": "HuggingFaceTB/SmolLM3-3B",
        },
        "model_load_ms": 10.0,
        "overall": {
            "FULL": {
                "candidate_selection_latency_ms_median": 1.5,
                "candidate_selection_latency_ms_p95": 1.8,
                "model_generation_latency_ms_median": 100.0,
                "task_pass_rate": 1.0,
            }
        },
        "rows": [
            {
                "task_id": "t1",
                "final_text": "done",
                "latency_ms": 50.0,
                "model_generation_latency_ms": 45.0,
                "episode_wall_latency_ms": 60.0,
                "candidate_selection_latency_ms": 1.0,
            }
        ],
    }
    sdpa = {
        "runtime": {"python": "3.12.14"},
        "model": {
            "attention_implementation": "sdpa",
            "static_prefix_cache": True,
            "name": "HuggingFaceTB/SmolLM3-3B",
        },
        "model_load_ms": 12.0,
        "overall": {
            "FULL": {
                "candidate_selection_latency_ms_median": 2.0,
                "candidate_selection_latency_ms_p95": 2.5,
                "model_generation_latency_ms_median": 90.0,
                "task_pass_rate": 1.0,
            }
        },
        "rows": [
            {
                "task_id": "t1",
                "final_text": "done",
                "latency_ms": 5.0,
                "model_generation_latency_ms": 4.0,
                "episode_wall_latency_ms": 6.0,
                "candidate_selection_latency_ms": 0.5,
            }
        ],
    }

    assert b2_compare._normalize(eager) == b2_compare._normalize(sdpa)


def test_normalization_preserves_behavioral_differences() -> None:
    eager = {
        "rows": [
            {
                "task_id": "t1",
                "passed": True,
                "final_text": "done",
                "tool_call_count": 1,
            }
        ]
    }
    sdpa = {
        "rows": [
            {
                "task_id": "t1",
                "passed": False,
                "final_text": "done",
                "tool_call_count": 1,
            }
        ]
    }

    assert b2_compare._normalize(eager) != b2_compare._normalize(sdpa)

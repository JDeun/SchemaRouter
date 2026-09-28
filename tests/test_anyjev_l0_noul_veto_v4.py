from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_anyjev_l0_noul_veto_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_anyjev_l0_noul_veto_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load AnyJev L0 diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_anyjev_protocol_is_pinned() -> None:
    module = _module()
    assert (
        module.ANYJEV_SOURCE_REVISION
        == "45add301a7aa60ed3420c83d15c061e84e5bce61"
    )
    assert module.BASE_MODEL == "Qwen/Qwen3-0.6B"
    assert (
        module.BASE_MODEL_REVISION
        == "c1899de289a04d12100db370d81485cdf75e47ca"
    )
    assert module.ACCEPTANCE_THRESHOLDS == (
        0.50,
        0.70,
        0.80,
        0.90,
        0.95,
        0.98,
        0.99,
        0.995,
    )


def test_anyjev_question_is_fixed_capability_language() -> None:
    module = _module()
    assert "fully execute" in module.QUESTION_TEXT
    assert "not topical similarity" in module.QUESTION_TEXT
    assert "Do not infer" in module.QUESTION_TEXT


def test_anyjev_state_contains_only_query_and_endpoint_contract() -> None:
    module = _module()
    state = module.build_state(
        {
            "query": "show current weather",
            "endpoint_contract": "Registered endpoint: weather.current",
            "expected": "weather.current",
            "language": "en",
            "unsupported_family": None,
        }
    )
    assert state == {
        "user_request": "show current weather",
        "endpoint_contract": "Registered endpoint: weather.current",
    }


def test_anyjev_threshold_metrics_use_full_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "raw_correct": True,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": "weather.forecast",
            "raw_correct": False,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": None,
            "raw_correct": False,
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "weather.family_1",
        },
        {
            "expected": None,
            "raw_correct": False,
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
        },
    ]

    result = module._evaluate_threshold(
        rows,
        [0.99, 0.99, 0.01, 0.01],
        0.90,
    )

    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0

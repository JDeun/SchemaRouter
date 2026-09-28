from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_qwen3_capability_verifier_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_qwen3_capability_verifier_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qwen3 capability verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Endpoint:
    name = "current"
    description = "Get current city temperature and conditions"
    operation_aliases = (
        "weather right now",
        "current weather",
        "live weather",
    )


class _Tool:
    key = "weather"
    description = "Weather observations and forecasts for cities"


def _row(
    *,
    expected: str | None,
    route: str,
    category: str,
    language: str = "en",
    family: str | None = None,
    raw_correct: bool | None = None,
) -> dict[str, object]:
    correct = (
        expected is not None and route == expected
        if raw_correct is None
        else raw_correct
    )
    return {
        "case_id": "case",
        "expected": expected,
        "raw_top_route": route,
        "raw_correct": correct,
        "category": category,
        "language": language,
        "unsupported_family": family,
    }


def test_external_model_and_revision_are_pinned() -> None:
    module = _module()
    assert module.QWEN_MODEL_NAME == "Qwen/Qwen3-Reranker-0.6B"
    assert (
        module.QWEN_MODEL_REVISION
        == "e61197ed45024b0ed8a2d74b80b4d909f1255473"
    )
    assert module.MAX_LENGTH == 256
    assert module.BATCH_SIZE == 8


def test_fixed_threshold_grid_has_eight_rules() -> None:
    module = _module()
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


def test_capability_contract_uses_only_registered_metadata() -> None:
    module = _module()
    contract = module._capability_contract(_Tool(), _Endpoint())
    assert "weather.current" in contract
    assert "Weather observations and forecasts for cities" in contract
    assert "Get current city temperature and conditions" in contract
    assert (
        "current weather, live weather, weather right now"
        in contract
    )
    assert "Unlisted operations are not supported" in contract


def test_instruction_explicitly_rejects_topical_similarity() -> None:
    module = _module()
    instruction = module.CAPABILITY_INSTRUCTION
    assert "exact operational capability" in instruction
    assert "not topical similarity" in instruction
    assert "Do not infer capabilities" in instruction
    assert "outside the explicit contract" in instruction


def test_input_format_contains_one_instruction_query_document() -> None:
    module = _module()
    value = module._format_verifier_input(
        "show pollen outlook",
        "Registered endpoint: weather.current",
    )
    assert value.count("<Instruct>:") == 1
    assert value.count("<Query>:") == 1
    assert value.count("<Document>:") == 1
    assert value.endswith(module.SUFFIX)


def test_threshold_metrics_keep_full_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
        ),
        _row(
            expected="weather.forecast",
            route="weather.current",
            category="v4_supported_natural",
            raw_correct=False,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="near_domain_unsupported_operation",
            family="weather.family_1",
        ),
        _row(
            expected=None,
            route="weather.current",
            category="out_of_domain",
        ),
    ]
    metrics = module._evaluate_threshold(
        rows,
        [0.99, 0.99, 0.01, 0.01],
        0.90,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["wrong_supported_accepted"] == 1
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0


def test_latency_sample_is_twenty_per_language() -> None:
    module = _module()
    rows = []
    for language in ("de", "en", "es", "ja", "ko", "mixed"):
        for index in range(25):
            rows.append(
                {
                    "case_id": f"{language}-{index}",
                    "language": language,
                }
            )
    selected = module._latency_sample_indexes(rows)
    assert len(selected) == 120
    selected_languages = [rows[index]["language"] for index in selected]
    for language in ("de", "en", "es", "ja", "ko", "mixed"):
        assert selected_languages.count(language) == 20

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_operation_routing_corpus.py"


def _module():
    spec = importlib.util.spec_from_file_location("audit_operation_routing_corpus", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load corpus audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(
    case_id: str,
    query: str,
    *,
    expected: str | None,
    language: str = "en",
    category: str = "test",
) -> dict:
    return {
        "id": case_id,
        "query": query,
        "expected": expected,
        "language": language,
        "category": category,
    }


def test_audit_detects_label_associated_tokens() -> None:
    module = _module()
    cases = [
        _case(
            f"supported-{index}",
            f"search papers about topic {index}",
            expected="papers.search",
        )
        for index in range(10)
    ]
    cases.extend(
        _case(
            f"unsupported-{index}",
            f"reject unsupported export request {index}",
            expected=None,
            category="near_domain_unsupported_operation",
        )
        for index in range(10)
    )

    result = module.audit(
        cases,
        min_docs=4,
        min_rate_gap=0.5,
        near_duplicate_threshold=0.95,
    )

    by_token = {item["token"]: item for item in result["label_token_gaps"]}
    assert by_token["unsupported"]["associated_label"] == "no_route"
    assert by_token["reject"]["associated_label"] == "no_route"
    assert by_token["search"]["associated_label"] == "supported"


def test_audit_reports_near_duplicate_template_pairs() -> None:
    module = _module()
    cases = [
        _case(
            "a",
            "please search papers about graph routing now",
            expected="papers.search",
        ),
        _case(
            "b",
            "please search papers about graph routing today",
            expected="papers.search",
        ),
        _case(
            "c",
            "show current weather in seoul",
            expected="weather.current",
        ),
    ]

    result = module.audit(
        cases,
        min_docs=99,
        near_duplicate_threshold=0.70,
    )

    assert result["near_duplicates"]["pair_count"] == 1
    pair = result["near_duplicates"]["examples"][0]
    assert {pair["left_id"], pair["right_id"]} == {"a", "b"}


def test_audit_reports_distribution_and_exact_duplicates() -> None:
    module = _module()
    cases = [
        _case(
            "same",
            "Search papers!",
            expected="papers.search",
            language="en",
        ),
        _case(
            "same",
            "search---papers",
            expected="papers.search",
            language="en",
        ),
        _case(
            "near",
            "지원하지 않는 작업",
            expected=None,
            language="ko",
            category="near_domain_unsupported_operation",
        ),
    ]

    result = module.audit(cases, min_docs=99)

    assert result["case_count"] == 3
    assert result["supported_count"] == 2
    assert result["no_route_count"] == 1
    assert result["duplicate_ids"] == 1
    assert result["duplicate_normalized_queries"] == 1
    assert result["language_counts"] == {"en": 2, "ko": 1}
    assert result["supported_route_counts"] == {"papers.search": 2}

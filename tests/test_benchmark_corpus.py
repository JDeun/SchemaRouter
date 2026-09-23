import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "decision-routing-v1.json"
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def _benchmark_module():
    spec = importlib.util.spec_from_file_location("benchmark_decision_routing", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_checked_in_benchmark_corpus_is_large_multilingual_and_adversarial() -> None:
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))

    assert len(cases) >= 100
    assert len({case["id"] for case in cases}) == len(cases)
    assert any(any("\uac00" <= char <= "\ud7a3" for char in case["query"]) for case in cases)
    assert any(case["expect_abstain"] for case in cases)
    assert {"normal", "near_duplicate", "multilingual_ko"}.issubset(
        {case["category"] for case in cases}
    )


def test_benchmark_loader_validates_corpus_against_reference_catalog() -> None:
    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    cases = module.load_corpus(CORPUS, allowed_routes=allowed)

    assert len(cases) >= 100
    assert all(case.expected in allowed for case in cases if not case.expect_abstain)
    assert all(case.expected is None for case in cases if case.expect_abstain)



def test_benchmark_keeps_final_route_accuracy_separate_from_abstention_recall() -> None:
    module = _benchmark_module()
    row = module.BenchmarkRow(
        backend="bounded",
        case_id="abstain",
        category="adversarial",
        query="out of domain",
        expected=None,
        predicted="weather.current",
        correct=False,
        invalid_plan=False,
        latency_ms=1.0,
        abstained=True,
        fallback_used=True,
    )

    summary = module.summarize([row])

    assert summary["accuracy"] == 0.0
    assert summary["expected_abstention_recall"] == 1.0
    assert summary["fallbacks"] == 1



def test_benchmark_html_report_is_self_contained_and_escapes_metadata(tmp_path) -> None:
    module = _benchmark_module()
    report = {
        "corpus": "<corpus>",
        "case_count": 2,
        "environment": {
            "system": "Darwin",
            "machine": "arm64",
            "python": "3.12",
            "hardware_label": "<script>alert(1)</script>",
        },
        "summary": {
            "keyword<script>": {
                "cases": 2,
                "accuracy": 0.5,
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "abstention_rate": 0.5,
                "mean_latency_ms": 1.25,
                "p50_latency_ms": 1.0,
                "p95_latency_ms": 1.5,
                "estimated_cost": None,
                "models": [],
                "requested_devices": ["cpu"],
                "actual_devices": ["cpu"],
            }
        },
    }

    html = module.render_html_report(report)

    assert "SchemaRouter decision benchmark" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "keyword&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "50.00%" in html
    assert "https://" not in html

    output = tmp_path / "benchmark.html"
    module._write_html(output, report)
    assert output.read_text(encoding="utf-8") == html


def test_benchmark_html_report_rejects_malformed_summary() -> None:
    module = _benchmark_module()

    try:
        module.render_html_report({"summary": []})
    except ValueError as exc:
        assert "summary must be an object" in str(exc)
    else:
        raise AssertionError("malformed benchmark summaries must fail closed")

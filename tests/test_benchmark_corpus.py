import hashlib
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
        "reproducibility": {
            "source_revision": "<revision-script>",
            "corpus_sha256": "<corpus-script>",
            "repeat": 1,
            "max_cases": None,
        },
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
                "accuracy_ci95": [0.236593, 0.763407],
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "expected_no_route_recall": 0.5,
                "expected_no_route_recall_ci95": [0.094531, 0.905469],
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
    assert "&lt;revision-" in html
    assert "&lt;corpus-sc" in html
    assert "<script>alert(1)</script>" not in html
    assert "50.00%" in html
    assert "23.66%–76.34%" in html
    assert "9.45%–90.55%" in html
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



def test_benchmark_summary_tracks_backend_invocation_coverage() -> None:
    module = _benchmark_module()
    rows = [
        module.BenchmarkRow(
            backend="bounded",
            case_id="called",
            category="normal",
            query="query",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            invalid_plan=False,
            latency_ms=1.0,
            backend_invoked=True,
        ),
        module.BenchmarkRow(
            backend="bounded",
            case_id="not-called",
            category="multilingual_ko",
            query="질문",
            expected=None,
            predicted=None,
            correct=True,
            invalid_plan=False,
            latency_ms=0.5,
            backend_invoked=False,
        ),
    ]

    summary = module.summarize(rows)

    assert summary["backend_invocations"] == 1
    assert summary["backend_invocation_rate"] == 0.5



def test_benchmark_reproducibility_digest_tracks_exact_corpus_bytes() -> None:
    module = _benchmark_module()

    assert module._corpus_sha256(CORPUS) == hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    smoke_digest = module._corpus_sha256(None)
    assert len(smoke_digest) == 64
    assert all(char in "0123456789abcdef" for char in smoke_digest)



def test_wilson_interval_handles_center_and_boundary_cases() -> None:
    module = _benchmark_module()

    assert module._wilson_interval(0, 0) is None
    assert module._wilson_interval(5, 10) == [0.236593, 0.763407]
    assert module._wilson_interval(0, 10) == [0.0, 0.277533]
    assert module._wilson_interval(10, 10) == [0.722467, 1.0]


def test_wilson_interval_rejects_invalid_success_count() -> None:
    module = _benchmark_module()

    for successes, total in [(-1, 10), (11, 10)]:
        try:
            module._wilson_interval(successes, total)
        except ValueError as exc:
            assert "successes" in str(exc)
        else:
            raise AssertionError("invalid binomial counts must fail")


def test_benchmark_summary_includes_binomial_confidence_intervals() -> None:
    module = _benchmark_module()
    rows = [
        module.BenchmarkRow(
            backend="bounded",
            case_id=f"case-{index}",
            category="normal" if index < 5 else "adversarial",
            query="query",
            expected=None if index >= 5 else "weather.current",
            predicted=(
                "weather.current"
                if index < 5
                else None if index < 8 else "weather.current"
            ),
            correct=index < 8,
            invalid_plan=False,
            latency_ms=1.0,
        )
        for index in range(10)
    ]

    summary = module.summarize(rows)

    assert summary["accuracy"] == 0.8
    assert summary["accuracy_ci95"] == [0.490162, 0.943318]
    assert summary["expected_no_route_recall"] == 0.6
    assert summary["expected_no_route_recall_ci95"] == [0.230724, 0.882379]
    assert summary["category_accuracy_ci95"]["normal"] == [0.565518, 1.0]
    assert summary["category_accuracy_ci95"]["adversarial"] == [0.230724, 0.882379]

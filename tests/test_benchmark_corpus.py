import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "decision-routing-v1.json"
CORPUS_V2 = ROOT / "benchmarks" / "decision-routing-v2.json"
CORPUS_V3 = ROOT / "benchmarks" / "decision-routing-v3.json"
CORPUS_V4 = ROOT / "benchmarks" / "decision-routing-v4-operation-holdout.json"
CORPUS_V5 = ROOT / "benchmarks" / "decision-routing-v5-operation-calibration.json"
CORPUS_V6 = ROOT / "benchmarks" / "decision-routing-v6-operation-holdout.json"
CORPUS_V7 = ROOT / "benchmarks" / "decision-routing-v7-operation-post-change-holdout.json"
CORPUS_V8 = ROOT / "benchmarks" / "decision-routing-v8-operation-alias-holdout.json"
GENERATOR_V2 = ROOT / "scripts" / "generate_decision_routing_v2.py"
GENERATOR_V3 = ROOT / "scripts" / "generate_decision_routing_v3.py"
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"
RESEARCH_WORKFLOW = ROOT / ".github" / "workflows" / "research-benchmark.yml"


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


def test_v2_corpus_is_large_balanced_split_and_multilingual() -> None:
    cases = json.loads(CORPUS_V2.read_text(encoding="utf-8"))

    assert len(cases) == 1200
    assert len({case["id"] for case in cases}) == 1200

    route_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for case in cases:
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1
        split_counts[case["split"]] = split_counts.get(case["split"], 0) + 1
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1

    assert route_counts["NO_ROUTE"] == 240
    assert all(
        count == 60
        for route, count in route_counts.items()
        if route != "NO_ROUTE"
    )
    assert split_counts == {"dev": 720, "calibration": 240, "test": 240}
    assert language_counts == {
        "en": 200,
        "ko": 200,
        "es": 200,
        "ja": 200,
        "de": 200,
        "mixed": 200,
    }


def test_v2_corpus_has_no_normalized_query_duplicates() -> None:
    import re

    cases = json.loads(CORPUS_V2.read_text(encoding="utf-8"))
    normalized = [
        re.sub(r"[^\w]+", "", case["query"].casefold())
        for case in cases
    ]

    assert len(normalized) == len(set(normalized))


def test_v2_loader_preserves_split_and_language() -> None:
    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    cases = module.load_corpus(CORPUS_V2, allowed_routes=allowed)

    assert len(cases) == 1200
    assert {case.split for case in cases} == {"dev", "calibration", "test"}
    assert {case.language for case in cases} == {
        "en",
        "ko",
        "es",
        "ja",
        "de",
        "mixed",
    }


def test_v2_generator_reproduces_checked_in_corpus_exactly() -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_v2",
        GENERATOR_V2,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    generated = module.build()
    module.validate(generated)
    checked_in = json.loads(CORPUS_V2.read_text(encoding="utf-8"))

    assert generated == checked_in


def test_benchmark_summary_tracks_split_and_language_accuracy() -> None:
    module = _benchmark_module()
    rows = [
        module.BenchmarkRow(
            backend="bounded",
            case_id="en-dev",
            category="normal",
            split="dev",
            language="en",
            query="query",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            invalid_plan=False,
            latency_ms=1.0,
        ),
        module.BenchmarkRow(
            backend="bounded",
            case_id="ko-test",
            category="normal",
            split="test",
            language="ko",
            query="질문",
            expected="weather.current",
            predicted=None,
            correct=False,
            invalid_plan=False,
            latency_ms=1.0,
        ),
    ]

    summary = module.summarize(rows)

    assert summary["split_accuracy"] == {"dev": 1.0, "test": 0.0}
    assert summary["language_accuracy"] == {"en": 1.0, "ko": 0.0}
    assert summary["routed_accuracy"] == 0.5
    assert summary["routed_accuracy_ci95"] is not None


def test_v3_holdout_is_balanced_multilingual_and_test_only() -> None:
    cases = json.loads(CORPUS_V3.read_text(encoding="utf-8"))

    assert len(cases) == 600
    assert len({case["id"] for case in cases}) == 600

    route_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for case in cases:
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        assert case["split"] == "test"

    assert route_counts["NO_ROUTE"] == 120
    assert all(
        count == 30
        for route, count in route_counts.items()
        if route != "NO_ROUTE"
    )
    assert language_counts == {
        "en": 100,
        "ko": 100,
        "es": 100,
        "ja": 100,
        "de": 100,
        "mixed": 100,
    }


def test_v3_holdout_has_no_exact_normalized_overlap_with_v2() -> None:
    import re

    v2 = json.loads(CORPUS_V2.read_text(encoding="utf-8"))
    v3 = json.loads(CORPUS_V3.read_text(encoding="utf-8"))

    def normalize(query: str) -> str:
        return re.sub(r"[^\w]+", "", query.casefold())

    v2_queries = {normalize(case["query"]) for case in v2}
    v3_queries = [normalize(case["query"]) for case in v3]

    assert len(v3_queries) == len(set(v3_queries))
    assert not (v2_queries & set(v3_queries))


def test_v3_generator_reproduces_checked_in_holdout_exactly() -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_decision_routing_v3",
        GENERATOR_V3,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    generated = module.build()
    module.validate(generated)
    checked_in = json.loads(CORPUS_V3.read_text(encoding="utf-8"))

    assert generated == checked_in


def test_v4_operation_holdout_is_balanced_multilingual_and_test_only() -> None:
    cases = json.loads(CORPUS_V4.read_text(encoding="utf-8"))

    assert len(cases) == 600
    assert len({case["id"] for case in cases}) == 600

    route_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for case in cases:
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        assert case["split"] == "test"

    assert route_counts["NO_ROUTE"] == 120
    assert all(
        count == 30
        for route, count in route_counts.items()
        if route != "NO_ROUTE"
    )
    assert language_counts == {
        "en": 100,
        "ko": 100,
        "es": 100,
        "ja": 100,
        "de": 100,
        "mixed": 100,
    }
    assert category_counts["near_domain_unsupported_operation"] == 96
    assert category_counts["out_of_domain"] == 24


def test_v4_operation_holdout_has_no_normalized_query_duplicates() -> None:
    import re

    cases = json.loads(CORPUS_V4.read_text(encoding="utf-8"))
    normalized = [
        re.sub(r"[^\w]+", "", case["query"].casefold())
        for case in cases
    ]

    assert len(normalized) == len(set(normalized))


def test_v4_operation_holdout_loads_against_reference_catalog() -> None:
    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    cases = module.load_corpus(CORPUS_V4, allowed_routes=allowed)

    assert len(cases) == 600
    assert sum(case.expect_abstain for case in cases) == 120
    assert all(case.split == "test" for case in cases)


def test_v4_operation_holdout_has_no_normalized_overlap_with_v2_or_v3() -> None:
    import re

    def normalized_queries(path: Path) -> set[str]:
        cases = json.loads(path.read_text(encoding="utf-8"))
        return {
            re.sub(r"[^\w]+", "", case["query"].casefold())
            for case in cases
        }

    v4 = normalized_queries(CORPUS_V4)

    assert v4.isdisjoint(normalized_queries(CORPUS_V2))
    assert v4.isdisjoint(normalized_queries(CORPUS_V3))


def test_v5_operation_calibration_is_balanced_multilingual_and_split() -> None:
    cases = json.loads(CORPUS_V5.read_text(encoding="utf-8"))

    assert len(cases) == 576
    assert len({case["id"] for case in cases}) == 576
    assert sum(case["split"] == "dev" for case in cases) == 384
    assert sum(case["split"] == "calibration" for case in cases) == 192
    assert sum(case["expected"] is None for case in cases) == 288

    language_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for case in cases:
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1

    assert language_counts == {
        "en": 96,
        "ko": 96,
        "es": 96,
        "ja": 96,
        "de": 96,
        "mixed": 96,
    }
    assert category_counts == {
        "operation_supported": 288,
        "near_domain_unsupported_operation": 288,
    }
    assert route_counts["NO_ROUTE"] == 288
    assert all(
        count == 18
        for route, count in route_counts.items()
        if route != "NO_ROUTE"
    )


def test_v6_operation_holdout_is_balanced_multilingual_and_test_only() -> None:
    cases = json.loads(CORPUS_V6.read_text(encoding="utf-8"))

    assert len(cases) == 600
    assert len({case["id"] for case in cases}) == 600
    assert all(case["split"] == "test" for case in cases)

    language_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for case in cases:
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1

    assert language_counts == {
        "en": 100,
        "ko": 100,
        "es": 100,
        "ja": 100,
        "de": 100,
        "mixed": 100,
    }
    assert category_counts == {
        "operation_supported_holdout": 384,
        "near_domain_unsupported_operation": 192,
        "out_of_domain": 24,
    }
    assert route_counts["NO_ROUTE"] == 216
    assert all(
        count == 24
        for route, count in route_counts.items()
        if route != "NO_ROUTE"
    )


def test_v5_v6_operation_corpora_load_against_reference_catalog() -> None:
    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }

    v5 = module.load_corpus(CORPUS_V5, allowed_routes=allowed)
    v6 = module.load_corpus(CORPUS_V6, allowed_routes=allowed)

    assert len(v5) == 576
    assert len(v6) == 600
    assert sum(case.expect_abstain for case in v5) == 288
    assert sum(case.expect_abstain for case in v6) == 216


def test_v5_v6_are_disjoint_from_prior_corpora_and_each_other() -> None:
    import re

    def normalized_queries(path: Path) -> set[str]:
        cases = json.loads(path.read_text(encoding="utf-8"))
        return {
            re.sub(r"[^\w]+", "", case["query"].casefold())
            for case in cases
        }

    prior = set()
    for path in (CORPUS_V2, CORPUS_V3, CORPUS_V4):
        prior.update(normalized_queries(path))

    v5 = normalized_queries(CORPUS_V5)
    v6 = normalized_queries(CORPUS_V6)

    assert len(v5) == 576
    assert len(v6) == 600
    assert v5.isdisjoint(prior)
    assert v6.isdisjoint(prior)
    assert v5.isdisjoint(v6)

def test_v7_operation_holdout_workflow_is_manual_and_threshold_gated() -> None:
    workflow = RESEARCH_WORKFLOW.read_text(encoding="utf-8")
    marker = "  operation-fit-v7-heldout-cpu:"
    assert marker in workflow
    holdout_job = workflow.split(marker, 1)[1]

    assert (
        "if: ${{ github.event_name == 'workflow_dispatch' "
        "&& inputs.run_operation_holdout "
        "&& inputs.operation_fit_min_similarity != '' }}"
        in holdout_job
    )
    assert "OPERATION_FIT_MIN_SIMILARITY: ${{ inputs.operation_fit_min_similarity }}" in holdout_job
    assert '--operation-fit-min-similarity "${OPERATION_FIT_MIN_SIMILARITY}"' in holdout_job
    assert "benchmarks/decision-routing-v7-operation-post-change-holdout.json" in holdout_job
    assert "benchmarks/decision-routing-v6-operation-holdout.json" not in holdout_job
    assert "--operation-fit-min-similarity 0.40" not in holdout_job



def test_v7_operation_post_change_holdout_is_balanced_multilingual_and_test_only() -> None:
    cases = json.loads(CORPUS_V7.read_text(encoding="utf-8"))

    assert len(cases) == 600
    assert len({case["id"] for case in cases}) == 600
    assert all(case["split"] == "test" for case in cases)

    language_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for case in cases:
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1

    assert language_counts == {
        "en": 100,
        "ko": 100,
        "es": 100,
        "ja": 100,
        "de": 100,
        "mixed": 100,
    }
    assert category_counts == {
        "operation_supported_post_change_holdout": 384,
        "near_domain_unsupported_operation": 192,
        "out_of_domain": 24,
    }
    assert route_counts["NO_ROUTE"] == 216
    assert all(count == 24 for route, count in route_counts.items() if route != "NO_ROUTE")


def test_v7_operation_post_change_holdout_loads_and_is_disjoint_from_prior_corpora() -> None:
    import re

    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = module.load_corpus(CORPUS_V7, allowed_routes=allowed)

    def normalized_queries(path: Path) -> set[str]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            re.sub(r"[^\w]+", "", case["query"].casefold())
            for case in raw
        }

    v7 = normalized_queries(CORPUS_V7)
    prior: set[str] = set()
    for path in (CORPUS_V2, CORPUS_V3, CORPUS_V4, CORPUS_V5, CORPUS_V6):
        prior.update(normalized_queries(path))

    assert len(cases) == 600
    assert sum(case.expect_abstain for case in cases) == 216
    assert len(v7) == 600
    assert v7.isdisjoint(prior)


def test_v8_operation_alias_holdout_is_balanced_multilingual_and_disjoint() -> None:
    import re

    cases = json.loads(CORPUS_V8.read_text(encoding="utf-8"))
    assert len(cases) == 600
    assert len({case["id"] for case in cases}) == 600
    assert all(case["split"] == "test" for case in cases)

    language_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for case in cases:
        language_counts[case["language"]] = language_counts.get(case["language"], 0) + 1
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1
        route = case["expected"] or "NO_ROUTE"
        route_counts[route] = route_counts.get(route, 0) + 1

    assert all(count == 100 for count in language_counts.values())
    assert category_counts == {
        "operation_supported_alias_holdout": 384,
        "near_domain_unsupported_operation": 192,
        "out_of_domain": 24,
    }
    assert route_counts["NO_ROUTE"] == 216
    assert all(count == 24 for route, count in route_counts.items() if route != "NO_ROUTE")

    def normalized_queries(path: Path) -> set[str]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {re.sub(r"[^\w]+", "", case["query"].casefold()) for case in raw}

    v8 = normalized_queries(CORPUS_V8)
    prior: set[str] = set()
    for path in (CORPUS_V2, CORPUS_V3, CORPUS_V4, CORPUS_V5, CORPUS_V6, CORPUS_V7):
        prior.update(normalized_queries(path))
    assert len(v8) == 600
    assert v8.isdisjoint(prior)


def test_v8_operation_alias_holdout_loads_against_reference_catalog() -> None:
    module = _benchmark_module()
    registry = module.reference_registry()
    allowed = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = module.load_corpus(CORPUS_V8, allowed_routes=allowed)
    assert len(cases) == 600
    assert sum(case.expect_abstain for case in cases) == 216

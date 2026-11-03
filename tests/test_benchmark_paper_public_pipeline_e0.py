"""Public Algorithm 1 planning profile is an E0 source-owned benchmark only."""
from __future__ import annotations

import json
from dataclasses import replace
from threading import current_thread, main_thread
from time import sleep

import pytest

from schemarouter.field_routing_session import SchemaFieldRoutingSession
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from scripts.benchmark_paper_public_pipeline_e0 import (
    EVIDENCE_TIER,
    benchmark,
    benchmark_load_profile,
    build_synthetic_public_case,
    main,
)


@pytest.mark.parametrize("hops", [1, 2])
def test_public_algorithm1_pipeline_e0_500_complete_plan_oracle(hops):
    report = benchmark(500, hops=hops, repeats=1, warmup=0)
    assert report["schema_version"] == 1
    assert report["evidence_tier"] == EVIDENCE_TIER
    assert report["registered_routes"] == 500
    assert report["expected_hops"] == hops
    assert len(report["expected_route_ids"]) == hops + 1
    assert report["strict_k"] == 5
    assert len(report["source_snapshot_id"]) == 64
    assert report["prepared_build_wall_ms"] >= 0
    assert report["prepared_build_process_cpu_ms"] >= 0
    for pathway in ("prepared_sync", "prepared_async_model_stub"):
        metrics = report[pathway]
        assert metrics["exact_route_oracle"] is True
        assert metrics["receipt_bytes"] > 0
        assert metrics["wall_ms"]["p50"] >= 0
        assert metrics["wall_ms"]["p95"] >= 0
        assert metrics["wall_ms"]["p99"] >= 0
        assert metrics["process_cpu_ms"]["p99"] >= 0
    assert report["prepared_async_model_stub"]["real_model_calls"] == 0
    assert report["prepared_async_model_stub"]["provider_calls"] == 0
    assert report["independent_e2_qualified"] is False
    assert report["provider_execution_performed"] is False
    assert report["model_latency_measured"] is False


@pytest.mark.parametrize(("routes", "hops"), [
    (0, 1), (499, 1), (5001, 1), (500, 0), (500, 3),
    (True, 1), (500, True),
])
def test_public_algorithm1_pipeline_e0_rejects_invalid_registered_shape(routes, hops):
    with pytest.raises(ValueError):
        build_synthetic_public_case(routes, hops)


@pytest.mark.parametrize(("repeats", "warmup"), [
    (0, 0), (21, 0), (True, 0), (1, -1), (1, 4), (1, True),
])
def test_public_algorithm1_pipeline_e0_rejects_unbounded_bench(repeats, warmup):
    with pytest.raises(ValueError):
        benchmark(500, hops=1, repeats=repeats, warmup=warmup)


@pytest.mark.parametrize(("routes", "hops"), [
    (500, 1), (500, 2), (5000, 2),
])
def test_public_algorithm1_refresh_profile_matches_cold_public_snapshot(routes, hops):
    report = benchmark(
        routes, hops=hops, repeats=2, warmup=0, measure_refresh=True,
    )
    assert report["schema_version"] == 2
    assert report["registered_routes"] == routes
    assert report["strict_k"] == 5
    refreshed = report["incremental_refresh"]
    assert refreshed["measured_changes"] == 2
    assert refreshed["registered_routes"] == routes
    assert refreshed["source_snapshot_matches_cold"] is True
    assert refreshed["stale_sessions_rejected"] is True
    assert refreshed["exact_route_oracle"] is True
    assert refreshed["expected_route_ids"] == report["expected_route_ids"]
    assert refreshed["model_calls"] == refreshed["provider_calls"] == 0
    for phase in ("journal_refresh", "cold_rebuild"):
        for measure in ("wall_ms", "process_cpu_ms"):
            assert set(refreshed[phase][measure]) == {"p50", "p95", "p99"}
            assert all(value >= 0 for value in refreshed[phase][measure].values())


@pytest.mark.parametrize("invalid", [0, 1, "true", None])
def test_public_algorithm1_refresh_profile_rejects_nonboolean_opt_in(invalid):
    with pytest.raises(ValueError):
        benchmark(500, repeats=1, warmup=0, measure_refresh=invalid)


def test_public_algorithm1_refresh_profile_rejects_graph_parity_drift(monkeypatch):
    """A postings-identical but different canonical graph must fail the E0 oracle."""
    original = NativeSchemaGraphIndex.refresh_from_inmemory_journal.__func__

    def corrupt_graph(cls, previous, registry):
        refreshed = original(cls, previous, registry)
        wrong = refreshed.graph.model_copy(deep=True)
        wrong.capability_ids = (*wrong.capability_ids, "unreviewed.ghost")
        return replace(refreshed, graph=wrong)

    monkeypatch.setattr(
        NativeSchemaGraphIndex, "refresh_from_inmemory_journal",
        classmethod(corrupt_graph),
    )
    with pytest.raises(AssertionError, match="graph|parity|snapshot"):
        benchmark(500, hops=2, repeats=1, warmup=0, measure_refresh=True)


@pytest.mark.parametrize("concurrency", [1, 4])
def test_load_profile_calls_real_public_paths_with_bounded_closed_loop(monkeypatch, concurrency):
    sync_calls = []
    async_calls = []
    original_sync = SchemaFieldRoutingSession.compile_understood
    original_async = SchemaFieldRoutingSession.acompile_query

    def compile_sync(self, *args, **kwargs):
        if current_thread() is not main_thread():
            sync_calls.append(1)
        return original_sync(self, *args, **kwargs)

    async def compile_async(self, *args, **kwargs):
        async_calls.append(1)
        return await original_async(self, *args, **kwargs)

    monkeypatch.setattr(SchemaFieldRoutingSession, "compile_understood", compile_sync)
    monkeypatch.setattr(SchemaFieldRoutingSession, "acompile_query", compile_async)
    report = benchmark_load_profile(100, requests=5, warmup=2, concurrency=concurrency)
    assert len(sync_calls) == len(async_calls) == 7
    assert report["registered_routes"] == 100
    assert report["evidence_tier"] == EVIDENCE_TIER
    assert report["slo_validated"] is report["independent_e2_qualified"] is False
    assert report["pinned_linux_run_qualified"] is False
    assert report["environment"]["logical_cpu_count"]
    assert "cgroup_v2_cpu_max" in report["environment"]
    for path in ("prepared_sync", "prepared_async_model_stub"):
        result = report[path]
        assert result["measured_calls"] == len(result["samples"]) == 5
        assert result["warmup_calls"] == 2
        assert result["max_outstanding_requests_observed"] == concurrency
        assert {s["request_id"] for s in result["samples"]} == set(range(5))
        assert len({s["client_id"] for s in result["samples"]}) == concurrency
        assert result["total_process_cpu_ms"] > 0
        assert result["process_peak_rss_raw"] > 0
        assert result["provider_calls"] == result["real_model_calls"] == 0
        assert result["percentiles_are_descriptive_not_slo_validation"]
        for sample in result["samples"]:
            assert sample["queue_ms"] >= 0
            assert sample["service_ms"] > 0
            assert sample["wall_ms"] == pytest.approx(sample["queue_ms"] + sample["service_ms"])
        for threshold in result["threshold_exceedances"]:
            assert threshold["sample_count"] == 5
            assert threshold["exceeded_count"] == sum(
                s["wall_ms"] > threshold["threshold_ms"] for s in result["samples"]
            )
    assert report["prepared_async_model_stub"]["model_stub_calls"] == 7
    assert report["prepared_sync"]["model_stub_calls"] == 0


@pytest.mark.parametrize("routes", [250, 500])
def test_load_profile_reuses_exact_source_catalog_sizes(routes):
    report = benchmark_load_profile(routes, requests=1, warmup=0)
    assert report["registered_routes"] == routes
    assert report["expected_route_ids"] == ["contact_directory.read", "case_service.read"]


def test_load_profile_includes_event_loop_cpu_queue_before_api_entry(monkeypatch):
    original = SchemaFieldRoutingSession.acompile_query

    async def blocking_compile(self, *args, **kwargs):
        sleep(0.015)  # Deliberately block the loop; later clients must report this wait.
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SchemaFieldRoutingSession, "acompile_query", blocking_compile)
    report = benchmark_load_profile(100, requests=4, warmup=0, concurrency=4, thresholds=(1,))
    result = report["prepared_async_model_stub"]
    assert result["samples"][1]["queue_ms"] >= 10
    assert all(s["service_ms"] >= 10 for s in result["samples"])
    assert result["threshold_exceedances"] == [
        {"threshold_ms": 1, "sample_count": 4, "exceeded_count": 4},
    ]


def test_load_profile_callback_failure_propagates_without_a_success_report(monkeypatch):
    from schemarouter import ModelAnalysisError

    original = SchemaFieldRoutingSession.acompile_query

    async def failed_model(payload):
        raise RuntimeError("callback failed")

    async def failed_compile(self, *args, **kwargs):
        kwargs["model"] = failed_model
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SchemaFieldRoutingSession, "acompile_query", failed_compile)
    with pytest.raises(ModelAnalysisError, match="model"):
        benchmark_load_profile(100, requests=5, warmup=0, concurrency=4)


@pytest.mark.parametrize("conditions", [
    {"routes": 5000}, {"routes": True}, {"requests": 0}, {"requests": 1001},
    {"requests": True}, {"warmup": 31}, {"warmup": -1}, {"concurrency": 2},
    {"concurrency": True}, {"thresholds": ()}, {"thresholds": (float("nan"),)},
    {"thresholds": (float("inf"),)}, {"thresholds": (-1,)}, {"thresholds": (True,)},
])
def test_load_profile_rejects_invalid_conditions_before_source_build(conditions):
    with pytest.raises(ValueError):
        benchmark_load_profile(**{"routes": 100, **conditions})


@pytest.mark.parametrize("argv", [
    ["--load-requests", "1"], ["--load-profile", "--routes", "500"],
    ["--load-profile", "--warmup", "0"], ["--load-profile", "--measure-refresh"],
])
def test_load_profile_cli_conditions_require_separate_opt_in(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2


def test_load_profile_cli_preserves_legacy_defaults_and_5000_options(monkeypatch, capsys):
    from scripts import benchmark_paper_public_pipeline_e0 as module

    calls = []

    def record(routes, **kwargs):
        calls.append((routes, kwargs))
        return {}

    monkeypatch.setattr(module, "benchmark", record)
    main([])
    main(["--routes", "5000", "--hops", "2", "--repeats", "1", "--warmup", "0"])
    assert calls == [
        (500, {"hops": 1, "repeats": 3, "warmup": 1, "measure_refresh": False}),
        (5000, {"hops": 2, "repeats": 1, "warmup": 0, "measure_refresh": False}),
    ]
    capsys.readouterr()


def test_load_profile_cli_defaults_to_six_cases_with_1000_requests_per_path(monkeypatch, capsys):
    from scripts import benchmark_paper_public_pipeline_e0 as module

    calls = []

    def record(routes, **kwargs):
        calls.append((routes, kwargs))
        return {}

    monkeypatch.setattr(module, "benchmark_load_profile", record)
    main(["--load-profile"])
    assert {(r, k["concurrency"]) for r, k in calls} == {
        (100, 1), (100, 4), (250, 1), (250, 4), (500, 1), (500, 4),
    }
    assert all(k["requests"] == 1000 and k["warmup"] == 30 for _, k in calls)
    assert len(json.loads(capsys.readouterr().out)["cases"]) == 6

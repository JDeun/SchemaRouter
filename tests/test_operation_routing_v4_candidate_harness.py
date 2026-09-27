from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.benchmark_decision_routing import BenchmarkRow

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_operation_routing_v4_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_operation_routing_v4_candidate",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load paired candidate benchmark")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(case_id: str, *, correct: bool, latency: float) -> BenchmarkRow:
    return BenchmarkRow(
        backend="x",
        case_id=case_id,
        category="v4_supported_natural",
        query="q",
        expected="weather.current",
        predicted="weather.current" if correct else None,
        correct=correct,
        invalid_plan=False,
        latency_ms=latency,
    )


def test_threshold_loader_validates_route_map() -> None:
    module = _module()
    assert module._load_thresholds('{"weather.current": 0.25}') == {
        "weather.current": 0.25
    }

    with pytest.raises(ValueError, match="non-empty"):
        module._load_thresholds("{}")
    with pytest.raises(ValueError, match="between 0 and 1"):
        module._load_thresholds('{"weather.current": 1.5}')


def test_paired_metrics_tracks_quality_and_latency_deltas() -> None:
    module = _module()
    baseline = [
        _row("a", correct=False, latency=10.0),
        _row("b", correct=True, latency=20.0),
    ]
    candidate = [
        _row("a", correct=True, latency=8.0),
        _row("b", correct=True, latency=18.0),
    ]

    result = module.paired_metrics(baseline, candidate)

    assert result["candidate_gains"] == 1
    assert result["candidate_losses"] == 0
    assert result["both_correct"] == 1
    assert result["both_wrong"] == 0
    assert result["latency_delta_mean_ms"] == pytest.approx(-2.0)
    assert result["latency_delta_p50_ms"] == pytest.approx(-2.0)
    assert result["latency_delta_p95_ms"] == pytest.approx(-2.0)


def test_paired_candidate_script_is_directly_executable() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--candidate-recall-limit" in completed.stdout
    assert "--candidate-thresholds-json" in completed.stdout

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_SCRIPT = ROOT / "scripts" / "render_benchmark_history.py"
REPORT_HELPER = ROOT / "scripts" / "compatibility_report.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_report(*, accuracy: float, hardware: str) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-09-23T12:00:00+00:00",
        "schemarouter_version": "0.7.0.dev0",
        "corpus": "benchmarks/decision-routing-v1.json",
        "reproducibility": {
            "source_revision": "abcdef1234567890",
            "corpus_sha256": "1234567890abcdef",
            "repeat": 1,
            "max_cases": None,
        },
        "environment": {"machine": "arm64", "hardware_label": hardware},
        "summary": {
            "keyword": {
                "cases": 144,
                "accuracy": accuracy,
                "accuracy_ci95": [0.70, 0.84],
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "expected_no_route_recall": 0.5,
                "expected_no_route_recall_ci95": [0.30, 0.70],
                "abstention_rate": 0.0,
                "p50_latency_ms": 1.0,
                "p95_latency_ms": 2.0,
                "estimated_cost": None,
                "models": [],
                "actual_devices": [],
            }
        },
    }


def test_benchmark_history_renders_multiple_escaped_runs(tmp_path) -> None:
    module = _load(HISTORY_SCRIPT, "render_benchmark_history")
    first = _sample_report(accuracy=0.75, hardware="<M4>")
    second = _sample_report(accuracy=0.80, hardware="RTX")

    html = module.render_history([("first<script>", first), ("second", second)])

    assert "SchemaRouter benchmark history" in html
    assert "75.00%" in html
    assert "80.00%" in html
    assert "70.00%–84.00%" in html
    assert "30.00%–70.00%" in html
    assert "abcdef123456" in html
    assert "1234567890ab" in html
    assert "first&lt;script&gt;" in html
    assert "&lt;M4&gt;" in html
    assert "<script>" not in html
    assert "https://" not in html

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(first), encoding="utf-8")
    assert module.load_report(report_path)["summary"]["keyword"]["cases"] == 144


def test_benchmark_history_rejects_empty_or_malformed_reports(tmp_path) -> None:
    module = _load(HISTORY_SCRIPT, "render_benchmark_history_invalid")

    try:
        module.render_history([])
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("empty history must fail closed")

    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    try:
        module.load_report(path)
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("non-object benchmark report must fail closed")


def test_compatibility_report_helper_writes_stable_metadata(tmp_path) -> None:
    module = _load(REPORT_HELPER, "compatibility_report_test")
    report = module.new_report(adapter="openapi", source="https://example.test/openapi.json")

    assert report["schema_version"] == 1
    assert report["adapter"] == "openapi"
    assert report["status"] == "pending"
    assert report["schemarouter_version"]
    assert report["environment"]["python"]

    report["status"] = "failure"
    report["error_type"] = "RuntimeError"
    output = tmp_path / "compatibility.json"
    module.write_report(output, report)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded["status"] == "failure"
    assert loaded["error_type"] == "RuntimeError"


def test_compatibility_workflow_retains_json_artifacts() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "compatibility.yml"
    ).read_text(encoding="utf-8")

    assert "--json-out artifacts/openapi-compatibility.json" in workflow
    assert "--json-out artifacts/optimade-compatibility.json" in workflow
    assert "pypi-${{ matrix.artifact-kind }}-compatibility.json" in workflow
    assert "pypi-framework-integrations-compatibility.json" in workflow
    assert '"schemarouter[langchain,langgraph,llamaindex]"' in workflow
    assert "--framework-integrations" in workflow
    assert (
        workflow.count(
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        )
        == 4
    )
    assert workflow.count("if: always()") == 4
    assert workflow.count("retention-days: 30") == 4

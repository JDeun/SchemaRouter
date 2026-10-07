from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "aggregate_compatibility_matrix.py"
    spec = importlib.util.spec_from_file_location("aggregate_compatibility_matrix", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(
    *,
    adapter: str,
    status: str = "success",
    evidence_kind: str = "live_public_provider",
) -> dict:
    return {
        "adapter": adapter,
        "source": f"https://{adapter}.example.test",
        "status": status,
        "generated_at": "2026-10-01T00:00:00+00:00",
        "schemarouter_version": "0.14.0.dev0",
        "details": {
            "evidence_kind": evidence_kind,
            "provider": f"{adapter} provider",
            "discovery_success": status == "success",
            "tool_count": 1,
            "endpoint_count": 2,
            "execution_bound": status == "success",
            "execution_success": status == "success",
            "safe_endpoint": "read",
            "returned_shape": "object",
            "discovery_latency_ms": 10.0,
            "execution_latency_ms": 20.0,
            "auth_required": False,
            "known_quirks": [],
        },
    }


def test_matrix_separates_public_and_reference_failures() -> None:
    module = _module()
    matrix = module.build_matrix(
        [
            _report(adapter="graphql", status="failure"),
            _report(
                adapter="mcp",
                status="failure",
                evidence_kind="pinned_reference_implementation",
            ),
            _report(adapter="odata"),
        ]
    )

    assert matrix["summary"] == {
        "total": 3,
        "success": 1,
        "failure": 2,
        "reference_failures": 1,
        "contract_failure": 1,
        "unavailable": 1,
        "skipped": 0,
        "unclassified_failure": 0,
    }
    classifications = {
        row["adapter"]: row["classification"]
        for row in matrix["adapters"]
    }
    assert classifications == {
        "graphql": "unavailable",
        "mcp": "contract_failure",
        "odata": "success",
    }


def test_markdown_matrix_is_stable_and_does_not_copy_exception_text() -> None:
    module = _module()
    report = _report(adapter="graphql", status="failure")
    report["error_type"] = "ConnectError"
    report["private_error_message"] = "Bearer secret-token"

    rendered = module.render_markdown(module.build_matrix([report]))

    assert "graphql" in rendered
    assert "ConnectError" in rendered
    assert "secret-token" not in rendered
    assert "external compatibility evidence" in rendered


def test_report_loader_normalizes_invalid_json_without_crashing(tmp_path: Path) -> None:
    module = _module()
    (tmp_path / "graphql-compatibility.json").write_text(
        "{not-json",
        encoding="utf-8",
    )

    reports = module._load_reports(tmp_path)
    matrix = module.build_matrix(reports)

    assert matrix["adapters"][0]["adapter"] == "graphql"
    assert matrix["adapters"][0]["status"] == "invalid_report"
    assert matrix["adapters"][0]["error_type"] == "JSONDecodeError"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "yes"),
        (False, "no"),
        (None, "—"),
    ],
)
def test_markdown_handles_tri_state_binding(value, expected: str) -> None:
    module = _module()
    report = _report(adapter="openrpc")
    report["details"]["execution_bound"] = value

    rendered = module.render_markdown(module.build_matrix([report]))

    assert f"| {expected} |" in rendered


def test_matrix_json_is_serializable() -> None:
    module = _module()
    matrix = module.build_matrix([_report(adapter="odata")])

    payload = json.dumps(matrix, sort_keys=True)

    assert '"adapter": "odata"' in payload


def test_required_reference_report_cannot_disappear_silently(tmp_path: Path) -> None:
    module = _module()

    reports = module._load_reports(
        tmp_path,
        required_reference_reports=("mcp-compatibility.json",),
    )
    matrix = module.build_matrix(reports)

    assert matrix["summary"]["reference_failures"] == 1
    assert matrix["adapters"][0]["status"] == "missing_report"
    assert matrix["adapters"][0]["classification"] == "contract_failure"
    assert matrix["adapters"][0]["error_type"] == "MissingReport"


def test_invalid_required_reference_report_is_contract_failure(tmp_path: Path) -> None:
    module = _module()
    (tmp_path / "openrpc-compatibility.json").write_text(
        "{broken",
        encoding="utf-8",
    )

    reports = module._load_reports(
        tmp_path,
        required_reference_reports=("openrpc-compatibility.json",),
    )
    matrix = module.build_matrix(reports)

    assert matrix["summary"]["reference_failures"] == 1
    assert matrix["adapters"][0]["classification"] == "contract_failure"


def test_skipped_status_remains_distinct_from_external_unavailability() -> None:
    module = _module()
    matrix = module.build_matrix(
        [
            _report(adapter="skipped-provider", status="skipped"),
            _report(adapter="offline-provider", status="failure"),
        ]
    )

    classifications = {
        row["adapter"]: row["classification"]
        for row in matrix["adapters"]
    }
    assert classifications["skipped-provider"] == "skipped"
    assert classifications["offline-provider"] == "unavailable"



def test_non_object_required_report_fails_closed(tmp_path: Path) -> None:
    module = _module()
    (tmp_path / "graphql-compatibility.json").write_text(
        "[]",
        encoding="utf-8",
    )

    reports = module._load_reports(
        tmp_path,
        required_reference_reports=("graphql-compatibility.json",),
    )
    matrix = module.build_matrix(reports)

    assert matrix["adapters"][0]["status"] == "invalid_report"
    assert matrix["adapters"][0]["error_type"] == "NonObjectReport"
    assert matrix["adapters"][0]["classification"] == "contract_failure"


def test_unknown_failure_remains_explicitly_unclassified() -> None:
    module = _module()
    report = _report(
        adapter="custom",
        status="failure",
        evidence_kind="unknown",
    )

    matrix = module.build_matrix([report])

    assert matrix["adapters"][0]["classification"] == "failure"
    assert matrix["summary"]["unclassified_failure"] == 1


def test_cli_required_reference_failure_returns_nonzero_and_writes_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "mcp-compatibility.json").write_text(
        json.dumps(
            _report(
                adapter="mcp",
                status="failure",
                evidence_kind="pinned_reference_implementation",
            )
        ),
        encoding="utf-8",
    )
    json_out = tmp_path / "matrix.json"
    markdown_out = tmp_path / "matrix.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aggregate_compatibility_matrix.py",
            "--reports-dir",
            str(reports),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--require-reference-success",
            "--required-reference-report",
            "mcp-compatibility.json",
        ],
    )

    assert module.main() == 2
    assert json.loads(json_out.read_text(encoding="utf-8"))["schema_version"] == 2
    assert "contract_failure" in markdown_out.read_text(encoding="utf-8")

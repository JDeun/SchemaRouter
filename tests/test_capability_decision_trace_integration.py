from __future__ import annotations

import json

from schemarouter import (
    CapabilityDecisionCandidateInput,
    SchemaRouter,
    build_capability_decision_trace,
    inspect_capability_decision_trace,
)
from schemarouter.cli import _run, build_parser
from schemarouter.dashboard import render_dashboard


def _trace():
    trace = build_capability_decision_trace(
        [
            CapabilityDecisionCandidateInput(
                capability_id="materials.optimade.summary",
                final_disposition="selected",
                retrieval="retrieved",
                health="healthy",
                drift="current",
                policy="allowed",
            ),
            CapabilityDecisionCandidateInput(
                capability_id="materials.rest.summary",
                final_disposition="excluded",
                retrieval="retrieved",
                health="unhealthy",
                drift="current",
                policy="allowed",
            ),
            CapabilityDecisionCandidateInput(
                capability_id="secret.admin.route",
                visible=False,
                final_disposition="excluded",
                policy="denied",
            ),
        ],
        snapshot_id="snapshot-1234567890",
        registry_version=4,
    )
    assert trace is not None
    return trace


def test_router_inspection_accepts_explicit_decision_traces_only() -> None:
    router = SchemaRouter()
    trace = _trace()

    without = router.inspect()
    with_trace = router.inspect(decision_traces=[trace])

    assert without.decision_traces == ()
    assert len(with_trace.decision_traces) == 1
    summary = with_trace.decision_traces[0]
    assert summary.trace_id == trace.trace_id
    assert summary.snapshot_id == "snapshot-1234567890"
    assert summary.registry_version == 4
    assert summary.candidate_count == 2
    assert [item.capability_id for item in summary.candidates] == [
        "materials.optimade.summary",
        "materials.rest.summary",
    ]
    assert "secret.admin.route" not in with_trace.model_dump_json()


def test_decision_trace_inspection_summary_is_privacy_safe() -> None:
    summary = inspect_capability_decision_trace(_trace())

    assert set(summary.model_fields) == {
        "trace_id",
        "snapshot_id",
        "registry_version",
        "candidate_count",
        "candidates",
    }
    serialized = summary.model_dump_json()
    for forbidden in (
        "secret.admin.route",
        "payload",
        "arguments",
        "credentials",
        "headers",
        "score",
        "rank",
    ):
        assert forbidden not in serialized


def test_dashboard_renders_compact_decision_trace_without_hidden_inventory() -> None:
    router = SchemaRouter()
    trace = _trace()
    inspection = router.inspect(decision_traces=[trace])

    html = render_dashboard(
        inspection.registry,
        live=inspection,
    )

    assert "Capability decision traces" in html
    assert "materials.optimade.summary:selected" in html
    assert "materials.rest.summary:excluded" in html
    assert "method_unhealthy" in html
    assert "secret.admin.route" not in html
    assert "snapshot-12" in html


def test_cli_inspects_serialized_decision_trace_compact_and_detailed(tmp_path) -> None:
    trace = _trace()
    document = tmp_path / "decision-trace.json"
    document.write_text(trace.model_dump_json(), encoding="utf-8")

    compact_args = build_parser().parse_args(
        ["inspect", "decision-trace", str(document), "--json"]
    )
    compact = json.loads(_run(compact_args))

    assert compact["trace_id"] == trace.trace_id
    assert compact["candidates"][0]["capability_id"] == "materials.optimade.summary"
    assert "operational" not in compact["candidates"][0]

    detailed_args = build_parser().parse_args(
        [
            "inspect",
            "decision-trace",
            str(document),
            "--detailed",
            "--json",
        ]
    )
    detailed = json.loads(_run(detailed_args))

    assert "operational" in detailed["candidates"][0]
    assert "secret.admin.route" not in json.dumps(detailed)

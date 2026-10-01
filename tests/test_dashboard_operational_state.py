from __future__ import annotations

from datetime import datetime, timezone

from schemarouter.dashboard import render_dashboard
from schemarouter.inspection import (
    ExecutionInspection,
    HealthProbeInspection,
    PlannerInspection,
    RegistryInspection,
    RouterInspection,
    SchemaWatchInspection,
)


def _empty_registry() -> RegistryInspection:
    return RegistryInspection(
        version=0,
        tool_count=0,
        endpoint_count=0,
        read_only_endpoints=0,
        mutating_endpoints=0,
        unclassified_endpoints=0,
        tools=[],
    )


def _live(execution: ExecutionInspection) -> RouterInspection:
    return RouterInspection(
        registry=_empty_registry(),
        planner=PlannerInspection(analyzer="KeywordAnalyzer"),
        execution=execution,
    )


def test_dashboard_renders_detailed_health_probe_state() -> None:
    checked = datetime(2026, 10, 1, 4, 30, tzinfo=timezone.utc)
    live = _live(
        ExecutionInspection(
            unavailable_access_paths=["down.read"],
            health_monitor_running=True,
            health_probes=[
                HealthProbeInspection(
                    tool="healthy",
                    endpoint="read",
                    status="healthy",
                    last_checked_at=checked,
                ),
                HealthProbeInspection(
                    tool="down",
                    endpoint="read",
                    status="unavailable",
                    last_checked_at=checked,
                    last_error_type="ConnectTimeout",
                ),
                HealthProbeInspection(
                    tool="unknown",
                    endpoint="read",
                    status="unknown",
                ),
            ],
        )
    )

    html = render_dashboard(live.registry, live=live)

    assert "Health monitor" in html
    assert "running" in html
    assert "healthy.read" in html
    assert "down.read" in html
    assert "unknown.read" in html
    assert "temporarily unavailable" in html
    assert "ConnectTimeout" in html
    assert "2026-10-01 04:30:00+00:00" in html
    assert "attention-row" in html


def test_dashboard_renders_schema_watch_pending_review_state() -> None:
    checked = datetime(2026, 10, 1, 4, 31, tzinfo=timezone.utc)
    applied = datetime(2026, 10, 1, 4, 20, tzinfo=timezone.utc)
    live = _live(
        ExecutionInspection(
            schema_watcher_running=True,
            schema_watches=[
                SchemaWatchInspection(
                    tool="materials",
                    status="applied",
                    interval_seconds=120,
                    apply_compatible=True,
                    last_checked_at=checked,
                    last_applied_at=applied,
                    last_compatibility="compatible",
                ),
                SchemaWatchInspection(
                    tool="papers",
                    status="pending_review",
                    interval_seconds=300,
                    apply_compatible=True,
                    last_checked_at=checked,
                    last_compatibility="breaking",
                    pending_review=True,
                    pending_change_count=3,
                ),
                SchemaWatchInspection(
                    tool="stale",
                    status="error",
                    interval_seconds=60,
                    apply_compatible=False,
                    last_checked_at=checked,
                    last_error_type="SchemaSourceError",
                ),
            ],
        )
    )

    html = render_dashboard(live.registry, live=live)

    assert "Schema watcher" in html
    assert "Schema watches" in html
    assert "materials" in html
    assert "compatible" in html
    assert "papers" in html
    assert "pending_review" in html
    assert ">yes<" in html
    assert ">3<" in html
    assert "breaking" in html
    assert "SchemaSourceError" in html


def test_dashboard_live_operational_tables_do_not_render_arbitrary_payloads() -> None:
    live = _live(
        ExecutionInspection(
            health_probes=[
                HealthProbeInspection(
                    tool="api",
                    endpoint="read",
                    status="unknown",
                    last_error_type="TimeoutError",
                )
            ],
            schema_watches=[
                SchemaWatchInspection(
                    tool="api",
                    status="idle",
                    interval_seconds=60,
                    apply_compatible=True,
                )
            ],
        )
    )

    html = render_dashboard(live.registry, live=live)

    assert "TimeoutError" in html
    assert "No health probes registered." not in html
    assert "No schema watches registered." not in html

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..errors import SchemaRouterError
from ..runs import RunEvent


class OpenTelemetryRunExporter:
    """Translate redacted SchemaRouter RunEvents into OpenTelemetry spans.

    Payloads, RunConfig metadata, and tags are intentionally not exported. The exporter records
    only structural execution attributes so enabling tracing does not silently weaken the default
    privacy boundary.
    """

    def __init__(self, tracer: Any | None = None) -> None:
        try:
            from opentelemetry import trace
        except ImportError as exc:
            raise ImportError(
                'OpenTelemetry support requires: pip install "schemarouter[otel]"'
            ) from exc

        self._trace = trace
        self.tracer = tracer or trace.get_tracer("schemarouter")
        self._run_spans: dict[str, Any] = {}
        self._tool_spans: dict[tuple[str, int, int], Any] = {}

    @staticmethod
    def _timestamp_ns(event: RunEvent) -> int:
        return int(event.timestamp.timestamp() * 1_000_000_000)

    def _run_attributes(self, event: RunEvent) -> dict[str, Any]:
        return {
            "schemarouter.run_id": event.run_id,
            "schemarouter.sequence": event.sequence,
        }

    def _tool_key(self, event: RunEvent) -> tuple[str, int, int] | None:
        primary = event.data.get("primary_call_index")
        candidate = event.data.get("fallback_candidate_index")
        if not isinstance(primary, int) or not isinstance(candidate, int):
            return None
        return event.run_id, primary, candidate

    def export(self, event: RunEvent) -> None:
        from opentelemetry.trace import Status, StatusCode

        timestamp = self._timestamp_ns(event)
        run_span = self._run_spans.get(event.run_id)

        if event.event == "run.start":
            if run_span is not None:
                raise SchemaRouterError(f"duplicate run.start for {event.run_id}")
            self._run_spans[event.run_id] = self.tracer.start_span(
                "schemarouter.run",
                start_time=timestamp,
                attributes=self._run_attributes(event),
            )
            return

        if run_span is None:
            raise SchemaRouterError(
                f"OpenTelemetry exporter received {event.event} before run.start"
            )

        if event.event == "plan.end":
            run_span.add_event(
                "plan.end",
                attributes={
                    "schemarouter.sequence": event.sequence,
                    "schemarouter.plan.call_count": int(event.data.get("call_count", 0)),
                    "schemarouter.plan.warning_count": len(event.data.get("warnings", [])),
                },
                timestamp=timestamp,
            )
            return

        if event.event == "tool.start":
            tool = event.tool
            endpoint = event.endpoint
            if tool is None or endpoint is None:
                raise SchemaRouterError("tool.start requires tool and endpoint")
            key = self._tool_key(event)
            if key is None:
                raise SchemaRouterError("tool.start requires stable call identity")
            if key in self._tool_spans:
                raise SchemaRouterError(
                    f"duplicate tool.start for {tool}.{endpoint}"
                )
            parent = self._trace.set_span_in_context(run_span)
            self._tool_spans[key] = self.tracer.start_span(
                f"schemarouter.tool {tool}.{endpoint}",
                context=parent,
                start_time=timestamp,
                attributes={
                    "schemarouter.run_id": event.run_id,
                    "schemarouter.sequence": event.sequence,
                    "schemarouter.tool": tool,
                    "schemarouter.endpoint": endpoint,
                    "schemarouter.primary_call_index": key[1],
                    "schemarouter.fallback_candidate_index": key[2],
                    "schemarouter.argument_count": len(event.data.get("argument_names", [])),
                    "schemarouter.selected_field_count": len(event.data.get("fields", [])),
                },
            )
            return

        if event.event in {"tool.end", "tool.error"}:
            key = self._tool_key(event)
            span = self._tool_spans.pop(key, None) if key is not None else None
            if span is None:
                raise SchemaRouterError(
                    f"{event.event} received without matching tool.start"
                )
            if event.event == "tool.error":
                error_type = str(event.data.get("error_type", "Error"))
                span.set_attribute("schemarouter.error_type", error_type)
                span.set_status(Status(StatusCode.ERROR, error_type))
            else:
                span.set_attribute(
                    "schemarouter.projected_field_count",
                    len(event.data.get("projected_fields", [])),
                )
            span.end(end_time=timestamp)
            return

        if event.event in {"run.end", "run.error"}:
            if event.event == "run.error":
                error_type = str(event.data.get("error_type", "Error"))
                run_span.set_attribute("schemarouter.error_type", error_type)
                run_span.set_attribute(
                    "schemarouter.error_stage",
                    str(event.data.get("stage", "unknown")),
                )
                run_span.set_status(Status(StatusCode.ERROR, error_type))
            else:
                run_span.set_attribute(
                    "schemarouter.result_count",
                    int(event.data.get("result_count", 0)),
                )
            run_span.end(end_time=timestamp)
            self._run_spans.pop(event.run_id, None)

            dangling = [
                key for key in self._tool_spans if key[0] == event.run_id
            ]
            for key in dangling:
                span = self._tool_spans.pop(key)
                span.set_status(Status(StatusCode.ERROR, "run ended with open tool span"))
                span.end(end_time=timestamp)
            return

    def close_runs(self, run_ids: set[str] | tuple[str, ...]) -> None:
        """End unfinished spans for selected runs without closing unrelated exporter state."""
        selected = set(run_ids)
        if not selected:
            return
        from opentelemetry.trace import Status, StatusCode

        dangling_tool_keys = [
            key for key in self._tool_spans
            if key[0] in selected
        ]
        for key in dangling_tool_keys:
            span = self._tool_spans.pop(key)
            span.set_status(
                Status(StatusCode.ERROR, "event stream ended before tool completion")
            )
            span.end()

        for run_id in tuple(selected):
            span = self._run_spans.pop(run_id, None)
            if span is None:
                continue
            span.set_status(
                Status(StatusCode.ERROR, "event stream ended before run completion")
            )
            span.end()

    def close(self) -> None:
        """End all unfinished spans owned by this exporter."""
        run_ids = set(self._run_spans)
        run_ids.update(key[0] for key in self._tool_spans)
        self.close_runs(run_ids)


async def _close_upstream_events(events: AsyncIterator[RunEvent]) -> None:
    close = getattr(events, "aclose", None)
    if close is None:
        return
    await close()


async def trace_run_events(
    events: AsyncIterator[RunEvent],
    *,
    exporter: OpenTelemetryRunExporter | None = None,
) -> AsyncIterator[RunEvent]:
    """Export an event stream while preserving ownership and upstream cleanup."""
    owns_exporter = exporter is None
    active = exporter or OpenTelemetryRunExporter()
    observed_run_ids: set[str] = set()
    primary_error: BaseException | None = None
    try:
        async for event in events:
            observed_run_ids.add(event.run_id)
            active.export(event)
            yield event
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        try:
            await _close_upstream_events(events)
        except BaseException as exc:
            cleanup_error = exc

        try:
            if owns_exporter:
                active.close()
            else:
                active.close_runs(observed_run_ids)
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc

        if primary_error is None and cleanup_error is not None:
            raise cleanup_error

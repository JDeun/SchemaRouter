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
        self._tool_spans: dict[tuple[str, str, str], Any] = {}

    @staticmethod
    def _timestamp_ns(event: RunEvent) -> int:
        return int(event.timestamp.timestamp() * 1_000_000_000)

    def _run_attributes(self, event: RunEvent) -> dict[str, Any]:
        return {
            "schemarouter.run_id": event.run_id,
            "schemarouter.sequence": event.sequence,
        }

    def _tool_key(self, event: RunEvent) -> tuple[str, str, str] | None:
        if event.tool is None or event.endpoint is None:
            return None
        return event.run_id, event.tool, event.endpoint

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
            key = self._tool_key(event)
            if key is None:
                raise SchemaRouterError("tool.start requires tool and endpoint")
            if key in self._tool_spans:
                raise SchemaRouterError(
                    f"duplicate tool.start for {event.tool}.{event.endpoint}"
                )
            parent = self._trace.set_span_in_context(run_span)
            self._tool_spans[key] = self.tracer.start_span(
                f"schemarouter.tool {event.tool}.{event.endpoint}",
                context=parent,
                start_time=timestamp,
                attributes={
                    "schemarouter.run_id": event.run_id,
                    "schemarouter.sequence": event.sequence,
                    "schemarouter.tool": event.tool,
                    "schemarouter.endpoint": event.endpoint,
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

    def close(self) -> None:
        """Fail closed if the supplied event sequence was incomplete."""
        if self._run_spans or self._tool_spans:
            raise SchemaRouterError("OpenTelemetry exporter has unfinished spans")


async def trace_run_events(
    events: AsyncIterator[RunEvent],
    *,
    exporter: OpenTelemetryRunExporter | None = None,
) -> AsyncIterator[RunEvent]:
    """Export an event stream to OpenTelemetry while preserving it for downstream consumers."""
    active = exporter or OpenTelemetryRunExporter()
    try:
        async for event in events:
            active.export(event)
            yield event
    finally:
        active.close()

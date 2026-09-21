import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    RunConfig,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events


def _tracer():
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    return provider.get_tracer("schemarouter-tests"), memory


def _router(*, fail: bool = False) -> SchemaRouter:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="current",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="city",
                            required=True,
                            json_schema={"type": "string"},
                        )
                    ],
                    output_fields=[
                        FieldSpec(name="city"),
                        FieldSpec(name="temperature"),
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "temperature": {"type": "integer"},
                        },
                        "required": ["city", "temperature"],
                    },
                )
            ],
        )
    )

    async def invoke(endpoint, arguments):
        if fail:
            raise RuntimeError("provider-secret-error")
        return {"city": arguments["city"], "temperature": 20}

    router.executor.bind("weather", invoke)
    return router


@pytest.mark.asyncio
async def test_otel_exporter_creates_parented_run_and_tool_spans_without_payloads() -> None:
    tracer, memory = _tracer()
    exporter = OpenTelemetryRunExporter(tracer)
    router = _router()

    events = trace_run_events(
        router.astream_events(
            PlanRequest(
                query="temperature",
                arguments={"city": "super-secret-city"},
            ),
            config=RunConfig(
                include_payloads=True,
                tags=["super-secret-tag"],
                metadata={"token": "super-secret-metadata"},
            ),
        ),
        exporter=exporter,
    )
    collected = [event async for event in events]

    assert collected[-1].event == "run.end"
    spans = memory.get_finished_spans()
    assert len(spans) == 2
    run_span = next(span for span in spans if span.name == "schemarouter.run")
    tool_span = next(span for span in spans if span.name.startswith("schemarouter.tool "))

    assert tool_span.parent is not None
    assert tool_span.parent.span_id == run_span.context.span_id
    assert run_span.status.status_code is StatusCode.UNSET
    assert tool_span.status.status_code is StatusCode.UNSET

    rendered = repr(
        [
            (span.name, dict(span.attributes), [(event.name, dict(event.attributes)) for event in span.events])
            for span in spans
        ]
    )
    assert "super-secret-city" not in rendered
    assert "super-secret-tag" not in rendered
    assert "super-secret-metadata" not in rendered
    assert "provider-secret-error" not in rendered


@pytest.mark.asyncio
async def test_otel_exporter_marks_tool_and_run_errors_without_exporting_messages() -> None:
    tracer, memory = _tracer()
    exporter = OpenTelemetryRunExporter(tracer)
    router = _router(fail=True)

    with pytest.raises(Exception):
        async for _ in trace_run_events(
            router.astream_events(
                PlanRequest(
                    query="temperature",
                    arguments={"city": "secret-city"},
                ),
                config=RunConfig(include_payloads=True),
            ),
            exporter=exporter,
        ):
            pass

    spans = memory.get_finished_spans()
    assert len(spans) == 2
    run_span = next(span for span in spans if span.name == "schemarouter.run")
    tool_span = next(span for span in spans if span.name.startswith("schemarouter.tool "))

    assert run_span.status.status_code is StatusCode.ERROR
    assert tool_span.status.status_code is StatusCode.ERROR
    rendered = repr([(dict(span.attributes), span.status.description) for span in spans])
    assert "secret-city" not in rendered
    assert "provider-secret-error" not in rendered

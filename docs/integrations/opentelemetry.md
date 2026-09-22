# OpenTelemetry

SchemaRouter can translate its typed runtime event stream into OpenTelemetry spans without adding an
OpenTelemetry dependency to the core package.

## Install

```bash
pip install --pre "schemarouter[otel]"
```

## Export a run

```python
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events

exporter = OpenTelemetryRunExporter()

async for event in trace_run_events(
    router.astream_events(request),
    exporter=exporter,
):
    # The same RunEvent stream is still available to the application.
    print(event.event)
```

The exporter creates:

```text
schemarouter.run
  └─ schemarouter.tool <tool>.<endpoint>
```

Tool errors mark the tool span as `ERROR`; run errors mark the run span as `ERROR`.

## Privacy boundary

The exporter is intentionally stricter than `RunConfig(include_payloads=True)`.

It exports structural attributes only, such as:

- run ID and sequence;
- tool and endpoint names;
- argument count and selected-field count;
- result count;
- error type and stage.

It does **not** export:

- argument values;
- result payloads;
- `RunConfig.metadata`;
- run tags;
- exception messages.

This means enabling OpenTelemetry does not silently turn on payload tracing.

## Bring your own provider/exporter

SchemaRouter only creates spans through a standard OpenTelemetry `Tracer`. Configure the global
provider/export pipeline normally, or pass an application-owned tracer:

```python
exporter = OpenTelemetryRunExporter(tracer=my_tracer)
```

OTLP, vendor exporters, sampling, and retention remain application concerns.

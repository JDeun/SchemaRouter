# OpenTelemetry

SchemaRouter는 core package에 OpenTelemetry dependency를 추가하지 않고 typed runtime event stream을 OpenTelemetry span으로 변환할 수 있습니다.

## 설치

```bash
pip install "schemarouter[otel]"
```

## Run export

```python
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events

exporter = OpenTelemetryRunExporter()

async for event in trace_run_events(
    router.astream_events(request),
    exporter=exporter,
):
    # 같은 RunEvent stream을 애플리케이션에서도 계속 사용할 수 있습니다.
    print(event.event)
```

생성되는 구조는 다음과 같습니다.

```text
schemarouter.run
  └─ schemarouter.tool <tool>.<endpoint>
```

tool error는 tool span을 `ERROR`로, run error는 run span을 `ERROR`로 표시합니다.

## Privacy 경계

exporter는 `RunConfig(include_payloads=True)`보다 엄격합니다. run ID/sequence, tool/endpoint 이름, argument 및 selected-field 수, result 수, error type/stage 같은 구조적 attribute만 내보냅니다.

다음은 export하지 않습니다.

- argument 값
- result payload
- `RunConfig.metadata`
- run tag
- exception message

따라서 OpenTelemetry를 활성화해도 payload tracing이 자동으로 켜지지 않습니다.

## 자체 provider/exporter 사용

SchemaRouter는 표준 OpenTelemetry `Tracer`를 통해서만 span을 만듭니다. global provider/export pipeline을 일반적인 방식으로 설정하거나 애플리케이션 소유 tracer를 전달할 수 있습니다.

```python
exporter = OpenTelemetryRunExporter(tracer=my_tracer)
```

OTLP, vendor exporter, sampling, retention은 애플리케이션이 관리합니다.

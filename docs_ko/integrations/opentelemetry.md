# OpenTelemetry

SchemaRouter는 핵심 패키지에 OpenTelemetry 의존성을 추가하지 않고도 타입 기반 런타임 이벤트 스트림을 OpenTelemetry span으로 변환할 수 있습니다.

## 설치

```bash
pip install "schemarouter[otel]"
```

## 실행 기록 내보내기

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

Exporter는 다음 span을 생성합니다.

```text
schemarouter.run
  └─ schemarouter.tool <tool>.<endpoint>
```

도구에서 오류가 발생하면 도구 span을 `ERROR`로 표시하고, 실행 전체에서 오류가 발생하면 실행 span을 `ERROR`로 표시합니다.

## 개인정보 보호 경계

Exporter의 정보 보호 수준은 `RunConfig(include_payloads=True)`보다 엄격합니다.

다음과 같은 구조적 속성만 내보냅니다.

- 실행 ID와 시퀀스 번호
- 도구와 엔드포인트 이름
- 인자 개수와 선택된 필드 개수
- 결과 개수
- 오류 유형과 발생 단계

다음 정보는 **내보내지 않습니다**.

- 인자 값
- 결과 페이로드
- `RunConfig.metadata`
- 실행 태그
- 예외 메시지

따라서 OpenTelemetry를 활성화해도 페이로드 추적이 암묵적으로 활성화되지 않습니다.

## 자체 공급자·Exporter 사용

SchemaRouter는 표준 OpenTelemetry `Tracer`를 통해서만 span을 생성합니다. 전역 공급자와 내보내기 파이프라인을 일반적인 방법으로 구성하거나 애플리케이션이 소유한 tracer를 직접 전달할 수 있습니다.

```python
exporter = OpenTelemetryRunExporter(tracer=my_tracer)
```

OTLP, 공급자별 Exporter, 샘플링, 보존 정책은 애플리케이션에서 담당합니다.

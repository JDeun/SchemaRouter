# 배치 실행, 스트리밍, 이벤트

SchemaRouter는 서로 다른 기능 소스에도 일관된 실행 용어와 인터페이스를 사용합니다.

## 호출

```python
result = router.invoke(request)
result = await router.ainvoke(request)
```

동기와 비동기 호출 모두 계획 수립과 실행을 수행합니다.

## 배치 실행

```python
results = router.batch(requests)
results = await router.abatch(
    requests,
    config={"max_concurrency": 8},
)
```

`abatch()`는 입력 순서를 보존합니다. 완료 순서대로 결과를 처리하려면 다음을 사용합니다.

```python
async for index, result in router.abatch_as_completed(requests):
    print(index, result)
```

반환된 인덱스는 언제나 원래 입력의 위치를 가리킵니다.

## 결과 스트리밍

```python
async for result in router.astream(request):
    print(result.tool, result.endpoint)
```

기본 실행 모드는 실행 계획의 순서를 보존하는 순차 실행입니다. 독립적인 읽기 전용 호출을 병렬로 처리하려면 `parallel_read_only`를 명시적으로 활성화합니다.

```python
from schemarouter import RunConfig

config = RunConfig(
    execution_mode="parallel_read_only",
    max_parallel_calls=4,
)

results = await router.ainvoke(request, config=config)
```

병렬 작업을 시작하기 전에 모든 계획된 호출에 대해 현재 스키마, 바인딩, 실행 정책을 사전 검증하고, 모든 엔드포인트의 `endpoint.read_only`가 `True`인지 확인합니다. 변경 작업이나 읽기·쓰기 여부가 불명확한 작업이 하나라도 있으면 실제 호출 전에 병렬 실행 전체를 거부합니다.

`ainvoke()`는 계획 순서로 결과를 반환하지만 `astream()`과 `astream_events()`에서는 완료 순서를 노출할 수 있으므로 먼저 끝난 읽기 전용 호출이 느린 형제 호출을 기다리지 않습니다. 모든 병렬 호출은 하나의 실행별 예산을 공유합니다. `max_parallel_calls`는 단일 계획의 병렬 호출 수를 제한하며, 배치 API에서 동시에 처리할 요청 수를 제한하는 `max_concurrency`와는 별개입니다.

이 기능은 단층 병렬 분기(flat fan-out)이며 DAG·워크플로 런타임이 아닙니다. 의존성, 분기, 체크포인트, 다단계 오케스트레이션은 LangGraph 등 상위 프레임워크가 담당합니다.

### 원자적 실행 바인딩 등록

`add_bound_tool()`, 실행 어댑터가 있는 URL 수용, Python·LangChain·LlamaIndex·HTTP 등록, MCP 등록처럼 기능 계약과 신뢰된 invoker를 함께 등록하는 공개 연산은 **실패 원자적인 단일 전환**으로 레지스트리 계약과 바인딩을 공개합니다.

바인딩이 실패하면 정확한 등록 이후 버전을 여전히 자신이 소유한 경우에만 이전 계약과 바인딩을 복원합니다. 신규 기능의 경우에는 새로 공개한 계약을 삭제합니다. 버전과 지문 검사로 롤백을 보호하므로 다른 동시 작성자의 수정을 바인딩 실패를 숨기는 목적으로 덮어쓰지 않습니다. 동시 변경으로 롤백이 안전하지 않으면 공개를 안전하게 실패시키고, 소유하지 않은 계약을 준비된 것으로 표시하는 대신 해당 바인딩을 제거합니다. 스키마 HTTP 검증기 등 공개 이후의 상태는 레지스트리·바인딩 전환에 성공한 다음에만 갱신합니다.

### 비동기 실행에서 동기 I/O 처리

신뢰된 동기 invoker는 기본적으로 호출 스레드에서 직접 실행합니다. 작업자 스레드에서 실행해도 안전하다고 호출자가 판단한 경우 `offload_sync=True`로 바인딩하면, 작업자를 기다리는 동안 남은 실행 시간 예산을 적용하고 이벤트 루프가 다른 작업을 처리할 수 있게 합니다.

공급자 중립적인 벡터·그래프·레코드 저장소도 `remote` 분류로 같은 규칙을 자동 적용합니다. `remote=True`인 백엔드의 동기 메서드는 작업자로 이관하지만 `remote=False`인 로컬 또는 특정 스레드에 결속된 백엔드는 직접 실행합니다. SQLite도 직접 실행합니다.

Python에서 이미 시작한 작업자 스레드를 강제로 종료할 수는 없습니다. 따라서 SchemaRouter는 무제한 `to_thread` 제출 대신 라우터가 소유한 **크기 제한 작업자 풀**에서 명시적인 동기 오프로드를 수행합니다. 시간 초과된 읽기 전용 호출은 백엔드가 반환할 때까지 슬롯을 점유할 수 있지만, 반복되는 타임아웃과 재시도로 작업자 부하가 무한정 증가하지는 않습니다. 모든 슬롯이 점유된 경우 새 오프로드는 차단 호출을 대기열에 계속 쌓는 대신 로컬 사용 불가 오류를 반환합니다.

읽기 전용이라고 명시한 엔드포인트가 경과 시간 예산을 넘으면 `ExecutionBudgetExceededError`가 발생합니다. 호출자는 백엔드가 반환하기 전까지 작업자가 계속 자원을 사용할 수 있음을 고려해야 합니다. 반면 변경 가능하거나 부작용을 알 수 없는 엔드포인트에서 작업자 시작 후 시간 초과나 취소가 발생하면 `IndeterminateInvocationError`가 발생합니다. **이는 재시도 불가 오류입니다.** 변경 작업이 이후에 실제로 완료될 수 있기 때문입니다. 더 강한 완료 보장이 필요하면 공급자별 타임아웃, 트랜잭션, 멱등성 키 또는 취소에 안전한 비동기 클라이언트를 사용하십시오.

## 타입 기반 수명주기 이벤트

```python
from schemarouter import RunConfig

async for event in router.astream_events(
    request,
    config=RunConfig(
        tags=["production"],
        metadata={"service": "research-agent"},
    ),
):
    print(event.sequence, event.event)
```

이벤트 수명주기는 다음과 같습니다.

```text
run.start
plan.end
tool.start
tool.end | tool.error
tool.fallback  # only after an explicitly unavailable precompiled read-only route
run.end  | run.error
```

하나의 호출에서 생성된 이벤트는 동일한 `run_id`와 단조 증가하는 `sequence`를 공유합니다. 공급자·접근 경로 폴백도 동일한 이벤트 스트림을 사용하고 무제한 재계획을 하지 않습니다. [공급자 인식 폴백](provider-fallback.md)을 참고하십시오.

## 라우터 소유 백그라운드 수명주기

SchemaRouter는 독립적인 백그라운드 작업 세 가지를 소유할 수 있습니다.

- 신뢰된 엔드포인트 상태 프로브를 위한 `AccessHealthMonitor`
- 원격 구조화 소스 스키마 갱신용 `SchemaWatchManager`
- 등록된 데이터베이스·벡터·그래프·레코드 새로고침 콜백을 처리하도록 `start_native_schema_watcher()`로 시작하는 네이티브 감시기

네이티브 기능 등록 시 새로고침 콜백은 저장하지만 감시기를 **자동으로 시작하지는 않습니다**. 주기적인 갱신이 필요하면 명시적으로 실행하십시오.

```python
await router.start_native_schema_watcher(interval_seconds=300)

# optional explicit shutdown
await router.stop_native_schema_watcher()
```

`SchemaRouter.aclose()`와 비동기 컨텍스트 매니저 종료는 세 가지 라우터 소유 작업을 모두 중지하려고 시도합니다. 종료는 멱등적이며 호출자가 소유하는 데이터베이스 클라이언트, SDK 클라이언트, 엔진 또는 전송 계층은 닫지 않습니다. 한 네이티브 스키마 소스가 예상치 못하게 실패해도 해당 소스에 격리하고 다음 순회에서 재시도하므로 나머지 소스의 감시기는 계속 동작합니다.

## 접근 경로 상태와 복구

재시도를 모두 소진해 `InvocationUnavailableError`를 일으킨 전송 경로는 **유한한 프로세스 내부 쿨다운**에 들어갑니다. 해당 시간이 만료되면 자동으로 다시 선택할 수 있습니다.

더 빠르게 복구하려면 명시적인 읽기 전용 경로에 신뢰된 상태 프로브를 등록합니다.

```python
router.register_health_probe(
    "mp_optimade",
    "search_structures",
    mp_optimade_health,
)

await router.start_health_monitor(
    interval_seconds=30,
    probe_timeout_seconds=5,
)

# during shutdown
await router.stop_health_monitor()
```

프로브가 성공하면 경로를 즉시 다시 열고, 실패하면 제한된 쿨다운만 연장합니다. SchemaRouter는 원격 메타데이터에서 프로브를 추측하지 않으며 모델 출력으로 상태를 바꿀 수도 없습니다. 별도의 서비스 상태 시스템을 사용하는 애플리케이션은 `mark_access_unavailable()`과 `mark_access_available()`을 직접 사용할 수 있습니다.

실시간 `router.inspect()`에는 쿨다운 경로, 프로브 상태, 모니터 실행 여부가 나타납니다. 정적 SQLite 레지스트리 검사로는 프로세스 로컬 상태를 알 수 없습니다.

## 페이로드 민감 정보 가림

기본적으로 인자와 결과 페이로드는 이벤트에 포함하지 않습니다. 페이로드 추적을 활성화하면 SchemaRouter는 이벤트를 전달하거나 저장하기 **전에** 구조화된 민감 정보를 가립니다.

```python
from schemarouter import RunConfig, TraceRedactionConfig

config = RunConfig(
    include_payloads=True,
    trace_redaction=TraceRedactionConfig(
        sensitive_paths={
            "data.arguments.customer.email",
            "data.result.data.customer.email",
        }
    ),
)
```

기본 키 매처는 비밀번호, API 키, 인증값, 쿠키, 토큰, 개인 키, 고위험 신원·결제 필드 등 일반적인 자격 증명 이름을 처리합니다. 대소문자를 구분하지 않고 `db_password` 같은 접두사도 감지합니다. 민감 키나 경로에서 발견한 값은 현재 실행 중 기억해 이후 예외 메시지에 같은 비밀이 등장하더라도 제거합니다. Bearer 토큰 및 문자열의 일반적인 `key=value` 자격 증명 형식도 가립니다.

`RunConfig.metadata`, 요청·계획 페이로드, 도구 인자, 결과, 예외 메시지에는 동일한 실행 범위 민감 정보 가림 처리를 적용합니다. Principal 권한 컨텍스트와 신뢰된 필터 값은 실행 이벤트에 추가하지 않습니다.

원시 페이로드 추적은 명시적인 디버깅 우회 설정으로만 사용할 수 있습니다.

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
)
```

`raw_trace_payloads=True`는 메타데이터 가림도 해제합니다. 자격 증명이나 개인정보가 그대로 영속 저장될 수 있으므로 신뢰된 수신처 및 적절한 보존·접근 제어가 있을 때만 사용하십시오.

## 설정을 결합한 라우터

```python
configured = router.with_config(
    RunConfig(
        tags=["service-a"],
        max_concurrency=4,
    )
)

await configured.ainvoke(request)
```

원래 라우터는 변경하지 않고 가벼운 설정 파사드(facade)를 생성합니다.

## OpenTelemetry

선택적 OpenTelemetry 연동도 동일한 타입 기반 이벤트 스트림을 사용합니다.

```python
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events

async for event in trace_run_events(
    router.astream_events(request),
    exporter=OpenTelemetryRunExporter(),
):
    ...
```

`include_payloads=True`여도 exporter는 페이로드 값, RunConfig 메타데이터, 태그, 예외 메시지를 포함하지 않습니다. [OpenTelemetry](../integrations/opentelemetry.md)를 참고하십시오.

## 실행 이벤트 영속화 및 재생

프로세스 재시작 이후에도 이벤트를 남겨야 하면 `SQLiteRunTraceStore`를 사용합니다.

```python
from schemarouter import SQLiteRunTraceStore

with SQLiteRunTraceStore("traces.sqlite3") as store:
    events = [
        event
        async for event in router.astream_events(
            request,
            trace_store=store,
        )
    ]
```

재생은 과거 이벤트만 읽고 도구를 재실행하지 않습니다. 개인정보 처리와 데이터 손상 대응, 수명주기는 [영속 실행 추적](run-traces.md)에서 설명합니다.

## 스키마 계획과 실행 가능 계획

`SchemaRouter.plan()`과 `aplan()`은 스키마 중심 API입니다. 구성된 접근 상태 조건을 고려하면서 어떤 등록 계약이 요청을 충족하는지 판단하지만, 그 시점에 신뢰된 invoker가 반드시 바인딩돼 있어야 하는 것은 아닙니다. 검사, 계약 작성 및 바인딩 이전의 계획 수립에 유용합니다.

실행용 API는 더 엄격한 경로를 선택합니다.

```python
schema_plan = router.plan(request)
execution_plan = router.plan_executable(request)

results = router.invoke(request)
```

`plan_executable()`과 `aplan_executable()`은 도구의 현재 지문과 일치하는 신뢰된 invoker 바인딩을 추가로 요구합니다. `invoke`, `ainvoke`, `stream`, `astream`, 배치 및 이벤트 스트림은 이 경로를 자동 사용합니다.

스키마 관점에서 유효해도 아직 바인딩되지 않은 선호 경로가 `router.plan()`에는 나타날 수 있습니다. 그러나 실행 시에는 필요한 필드를 똑같이 제공하면서 정상 상태이고 바인딩된 다른 경로를 선택할 수 있습니다.

명시적인 `execute(plan)`은 재계획하지 않습니다. 제공된 계획과 미리 컴파일된 폴백 경로를 통상적인 안전 거부형 스키마·바인딩·정책 규칙으로 검증하여 실행합니다.

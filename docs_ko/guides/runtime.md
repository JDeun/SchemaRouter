# 배치, 스트리밍 및 이벤트

SchemaRouter는 기능 제공원에 관계없이 일관된 실행 용어와 인터페이스를 사용합니다.

## 단일 요청 실행

```python
result = router.invoke(request)
result = await router.ainvoke(request)
```

두 인터페이스 모두 요청에 대한 계획 수립과 실행을 수행합니다.

## 배치 실행

```python
results = router.batch(requests)
results = await router.abatch(
    requests,
    config={"max_concurrency": 8},
)
```

`abatch()`는 입력 요청의 순서를 보존합니다.

완료된 순서대로 결과를 소비하려면 다음과 같이 호출합니다.

```python
async for index, result in router.abatch_as_completed(requests):
    print(index, result)
```

반환되는 인덱스는 언제나 원래 입력 배열에서의 위치를 가리킵니다.

## 결과 스트리밍

```python
async for result in router.astream(request):
    print(result.tool, result.endpoint)
```

기본 실행 모드는 순차 실행이며 계획된 호출 순서를 유지합니다.

서로 독립적인 읽기 전용 작업을 병렬로 실행하려면 `parallel_read_only`를 명시적으로 사용합니다.

```python
from schemarouter import RunConfig

config = RunConfig(
    execution_mode="parallel_read_only",
    max_parallel_calls=4,
)

results = await router.ainvoke(request, config=config)
```

병렬 작업을 하나라도 시작하기 전에 SchemaRouter는 계획에 포함된 **모든 호출**을 현재 스키마, 바인딩, 실행 정책으로 사전 검증하고, 전부 `endpoint.read_only is True`인지 확인합니다. 변경 작업이나 부작용이 분류되지 않은 호출이 하나라도 있으면 실제 호출 전에 병렬 실행 전체가 실패합니다.

`ainvoke()`는 계획 순서로 결과를 반환합니다. `astream()`과 `astream_events()`는 완료 순서로 결과를 노출할 수 있으므로 느린 읽기 작업 때문에 먼저 끝난 작업의 반환이 지연되지 않습니다. 모든 병렬 호출은 실행별로 설정한 동일한 예산을 공유합니다. `max_parallel_calls`는 하나의 계획 내부에서 병렬 실행할 호출 수를 제한하며, 배치 API에서 동시에 처리할 입력 수를 제한하는 `max_concurrency`와 별개입니다.

이 기능은 평면적인 병렬 호출 확장(fan-out)일 뿐 DAG 또는 워크플로 런타임이 아닙니다. 의존성, 분기, 체크포인트, 다단계 오케스트레이션은 LangGraph 등 상위 프레임워크의 책임입니다.

### 바인딩이 포함된 등록의 원자성

`add_bound_tool()`, 실행 가능한 어댑터를 통한 URL 등록, Python·LangChain·LlamaIndex·HTTP 등록, MCP 등록처럼 기능 계약과 신뢰된 invoker를 함께 등록하는 공개 API는 레지스트리 계약과 바인딩을 **실패 원자적(failure-atomic) 전환**으로 공개합니다.

바인딩에 실패하면 SchemaRouter가 방금 기록한 정확한 레지스트리 버전을 여전히 소유하고 있을 때에만 이전 계약과 바인딩을 복원합니다. 새 기능이라면 방금 공개한 계약을 제거합니다. 롤백은 레지스트리 버전과 지문 확인으로 보호되므로, 바인딩 실패를 감추기 위해 동시 작성자의 변경을 덮어쓰지 않습니다.

동시에 발생한 계약 변경 때문에 안전한 롤백이 불가능하면 공개 작업은 안전하게 실패하고, 소유권이 없는 계약의 바인딩을 준비 완료 상태로 남겨 두지 않고 제거합니다. 스키마 HTTP 검증기 및 기타 공개 후 상태는 레지스트리와 바인딩의 전환이 모두 성공한 뒤에만 갱신합니다.

### 비동기 실행 내부의 동기 I/O

신뢰된 동기 invoker는 기본적으로 현재 실행 흐름에서 직접 실행됩니다. 호출자가 해당 invoker를 워커 스레드에서 안전하게 실행할 수 있음을 알고 있다면 `offload_sync=True`로 바인딩하십시오. 그러면 SchemaRouter는 이벤트 루프의 응답성을 유지하고 워커를 기다리는 동안 남은 실행 시간 예산을 적용합니다.

공급자에 종속되지 않는 벡터·그래프·레코드 저장소 백엔드는 `remote` 분류에 따라 동일한 규칙을 자동 적용합니다. `remote=True` 백엔드의 동기 메서드는 오프로드하지만, `remote=False`인 로컬 또는 스레드 종속 백엔드는 직접 실행합니다. SQLite 역시 직접 실행합니다.

Python은 이미 시작한 워커 스레드를 강제로 중단할 수 없습니다. 따라서 SchemaRouter는 무제한으로 `to_thread` 작업을 제출하지 않고, 크기가 제한된 라우터 소유 워커 풀에서 명시적인 동기 오프로드를 실행합니다. 시간 초과된 읽기 전용 호출도 백엔드가 반환할 때까지 워커 슬롯 하나를 계속 사용할 수 있습니다. 그러나 시간 초과와 재시도가 반복되더라도 라우터에서 발생한 워커 점유량이 무제한으로 증가하지 않습니다. 모든 슬롯이 점유됐으면 새로운 오프로드를 대기열에 계속 넣는 대신 로컬에서 사용할 수 없는 상태로 실패합니다.

명시적으로 읽기 전용인 엔드포인트의 실행 시간 초과는 여전히 `ExecutionBudgetExceededError`를 발생시킵니다. 다만 백엔드 호출이 반환될 때까지 해당 워커가 리소스를 사용할 수 있다는 점을 호출자가 고려해야 합니다. 읽기 전용이 아니거나 부작용을 알 수 없는 엔드포인트는 워커가 시작된 후 시간 초과 또는 작업 취소가 발생하면 `IndeterminateInvocationError`를 발생시킵니다. 이 오류는 재시도할 수 없습니다. 변경 작업이 나중에 완료될 수도 있으므로 SchemaRouter가 같은 호출을 자동 반복하지 않습니다.

더 강력한 완료 보장이 필요하면 공급자 자체의 타임아웃, 트랜잭션, 멱등성 키 또는 취소에 안전한 비동기 클라이언트를 사용해야 합니다.

## 타입이 정의된 수명주기 이벤트

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

이벤트 수명주기에는 다음 항목이 포함됩니다.

```text
run.start
plan.end
tool.start
tool.end | tool.error
tool.fallback  # only after an explicitly unavailable precompiled read-only route
run.end  | run.error
```

하나의 호출에서 발생하는 모든 이벤트는 동일한 `run_id`와 단조 증가하는 `sequence`를 공유합니다.

공급자 또는 접근 경로의 대체 동작도 동일한 이벤트 스트림을 사용하며 제한 없는 재계획을 수행하지 않습니다. [공급자 인식 대체 경로](provider-fallback.md)를 참고하십시오.

## 라우터가 소유하는 백그라운드 수명주기

SchemaRouter는 서로 독립적인 세 종류의 백그라운드 활동을 소유할 수 있습니다.

- 신뢰된 엔드포인트 상태 프로브용 `AccessHealthMonitor`
- 원격 구조화 소스의 스키마 새로고침을 위한 `SchemaWatchManager`
- 등록된 데이터베이스·벡터·그래프·레코드 저장소의 새로고침 콜백을 위한 `start_native_schema_watcher()` 기반 네이티브 스키마 감시기

네이티브 기능을 등록하면 새로고침 콜백은 기록하지만 감시기가 자동으로 시작되지는 않습니다. 주기적 새로고침이 필요하면 명시적으로 시작해야 합니다.

```python
await router.start_native_schema_watcher(interval_seconds=300)

# optional explicit shutdown
await router.stop_native_schema_watcher()
```

`SchemaRouter.aclose()` 및 비동기 컨텍스트 매니저 종료는 반환 전에 라우터 소유의 세 가지 백그라운드 활동을 모두 중지하려고 시도합니다. 종료는 반복 호출해도 안전하며, 호출자가 소유한 데이터베이스 클라이언트·SDK 클라이언트·엔진·전송 계층은 SchemaRouter가 닫지 않습니다. 하나의 네이티브 스키마 소스에서 예상하지 못한 오류가 발생하면 해당 소스로 격리되어 다음 감시 주기에 재시도되며, 다른 등록 소스를 위한 감시기까지 중단하지는 않습니다.

## 접근 경로의 상태 확인과 복구

전송 경로가 재시도 횟수를 소진하고 `InvocationUnavailableError`를 발생시키면 프로세스 내부에서 유한한 쿨다운 기간에 들어갑니다. 해당 기간이 끝나면 자동으로 다시 후보가 될 수 있습니다.

더 빠른 복구가 필요하다면 명시적으로 읽기 전용인 경로에 신뢰된 프로브를 등록할 수 있습니다.

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

프로브에 성공하면 경로를 즉시 다시 열고, 실패하면 제한된 쿨다운만 연장합니다. SchemaRouter는 원격 메타데이터에서 프로브를 임의로 만들어 내지 않으며 모델 출력으로 상태를 변경하도록 허용하지 않습니다. 별도 서비스 상태 시스템을 운영하는 애플리케이션은 `mark_access_unavailable()`과 `mark_access_available()`을 직접 호출할 수 있습니다.

실시간 `router.inspect()`에는 현재 쿨다운 경로, 프로브 상태, 모니터 실행 여부가 표시됩니다. 정적인 SQLite 레지스트리 검사로는 프로세스 내부의 상태를 확인할 수 없습니다.

## 페이로드의 민감 정보 가림

기본적으로 인자 및 결과 페이로드는 이벤트에 포함되지 않습니다. 페이로드 추적을 활성화하더라도 SchemaRouter는 이벤트를 전달하거나 영속화하기 **전에** 구조화된 추적 내용의 민감 정보를 가립니다.

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

기본 키 탐지기는 비밀번호, API 키, 인증값, 쿠키, 토큰, 개인 키 및 일부 고위험 신원·결제 필드를 감지합니다. 대소문자를 구분하지 않고 `db_password`처럼 접두사가 있는 일반적인 이름도 처리합니다. 민감 키나 경로에서 발견한 값은 해당 실행 중에 기억하여 이후 예외 메시지에 같은 값이 등장하면 제거합니다. 문자열의 Bearer 토큰과 일반적인 `key=value` 형식의 자격 증명도 제거합니다.

`RunConfig.metadata`, 요청·계획 페이로드, 도구 인자, 결과, 예외 메시지는 동일한 실행 범위의 가림 처리기를 통과합니다. Principal 권한 컨텍스트와 신뢰된 필터 값은 실행 이벤트에 추가하지 않습니다.

원시 페이로드 추적은 디버깅을 위해 명시적으로 활성화하는 경우에만 사용할 수 있습니다.

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
)
```

`raw_trace_payloads=True`는 메타데이터 가림도 비활성화합니다. 자격 증명과 개인정보가 그대로 영속화될 수 있으므로 신뢰 가능한 수신 대상과 적절한 보존·접근 통제를 적용한 경우에만 사용하십시오.

## 설정이 바인딩된 실행 인터페이스

```python
configured = router.with_config(
    RunConfig(
        tags=["service-a"],
        max_concurrency=4,
    )
)

await configured.ainvoke(request)
```

기존 라우터를 변경하지 않고 설정이 적용된 가벼운 파사드를 생성합니다.

## OpenTelemetry

선택적인 OpenTelemetry 통합은 동일한 타입 기반 이벤트 스트림을 소비합니다.

```python
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events

async for event in trace_run_events(
    router.astream_events(request),
    exporter=OpenTelemetryRunExporter(),
):
    ...
```

Exporter는 `include_payloads=True`일 때도 페이로드 값, RunConfig 메타데이터, 태그, 예외 메시지를 제외합니다. [OpenTelemetry](../integrations/opentelemetry.md)를 참고하십시오.

## 이벤트 추적 기록의 영속화와 재생

프로세스가 재시작된 후에도 이벤트 스트림을 보존해야 한다면 `SQLiteRunTraceStore`를 사용합니다.

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

재생은 과거 이벤트만 읽으며 도구를 다시 실행하지 않습니다. 개인정보 보호, 손상 처리, 수명주기 동작은 [영속 실행 추적 기록](run-traces.md)에 설명되어 있습니다.

## 스키마 계획과 실행 준비 계획의 차이

`SchemaRouter.plan()`과 `aplan()`은 스키마 중심으로 작동합니다. 설정된 접근 경로의 상태 조건을 고려하여 요청을 충족할 수 있는 등록 계약을 찾지만, 해당 시점에 신뢰된 invoker의 바인딩을 반드시 요구하지는 않습니다. 검사, 계약 작성, 바인딩 이전의 계획 수립에 유용합니다.

실제 실행을 위한 API는 더 엄격한 경로 집합을 사용합니다.

```python
schema_plan = router.plan(request)
execution_plan = router.plan_executable(request)

results = router.invoke(request)
```

`plan_executable()`과 `aplan_executable()`에는 도구의 현재 지문에 연결된 신뢰된 invoker가 존재해야 한다는 로컬 제약이 추가됩니다. `invoke`, `ainvoke`, `stream`, `astream`, 배치 API, 타입 기반 이벤트 스트림은 실행 준비 계획 경로를 자동으로 사용합니다.

스키마 관점에서 유효하지만 현재 바인딩되지 않은 선호 경로는 `router.plan()` 결과에 나타날 수 있습니다. 반면 실제 실행 경로는 동일한 요청 필드를 제공할 수 있는 정상 상태의 바인딩된 다른 경로를 선택할 수 있습니다.

명시적으로 호출한 `execute(plan)`은 재계획하지 않습니다. 전달받은 계획을 일반적인 바인딩·스키마·정책의 안전한 거부 규칙과 미리 컴파일된 대체 경로에 따라 검증하고 실행합니다.

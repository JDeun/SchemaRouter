# 영속 실행 추적 기록

SchemaRouter는 타입이 명시된 `RunEvent` 스트림을 SQLite에 영속 저장할 수 있습니다. 도구 호출을 다시 실행하지 않고도 감사, 디버깅, 재생(replay)에 활용합니다.

## 추적 기록 저장소 만들기

```python
from schemarouter import SQLiteRunTraceStore

store = SQLiteRunTraceStore("schemarouter-traces.sqlite3")
```

이 저장소는 Python 표준 라이브러리의 `sqlite3` 모듈만 사용하며 새로운 패키지 의존성을 필요로 하지 않습니다.

## 런타임에서 직접 영속화하기

```python
events = [
    event
    async for event in router.astream_events(
        request,
        trace_store=store,
    )
]

run_id = events[0].run_id
trace = store.trace(run_id)
```

이벤트는 하위 소비자에게 전달되기 전에 먼저 저장됩니다. 따라서 영속화 오류가 발생하면 추적 기록을 생성하는 스트림 자체가 실패합니다. 실행 이력이 누락되었는데도 정상적인 감사 기록이 남은 것처럼 조용히 넘어가지 않습니다.

## 실행하지 않고 재생하기

```python
from schemarouter import replay_run_events

for event in replay_run_events(store, run_id):
    print(event.sequence, event.event)
```

재생은 과거에 기록된 유효한 `RunEvent` 객체만 읽습니다. 플래너, 실행기, 네트워크, 등록된 도구 invoker를 **호출하지 않습니다**.

## 추적 기록의 불변식

영속화된 실행 기록은 다음 요구사항을 만족해야 합니다.

- 시퀀스 번호 0의 `run.start`로 시작합니다.
- 하나의 불변 `run_id`를 유지합니다.
- 시퀀스 번호가 끊기지 않고 연속됩니다.
- 타임스탬프가 단조 증가하거나 유지됩니다.
- 두 번째 `run.start`를 포함하지 않습니다.
- `run.end` 또는 `run.error` 이후에는 이벤트를 추가하지 않습니다.

손상된 JSON, 이벤트 식별자 불일치, 시퀀스 공백, 타임스탬프 역행, 종료 이벤트 이후 추가는 `TraceError`로 안전하게 거부합니다.

**미완료 기록은 허용합니다.** 프로세스가 종료 이벤트를 기록하기 전에 중단된 상황을 분석하는 데 유용합니다.

```python
store.run_ids(complete=True)
store.run_ids(complete=False)
```

## 보존 정책과 정리(pruning)

기존 애플리케이션의 저장 동작이 달라지지 않도록 보존 정책은 명시적으로 설정해야 합니다.

```python
from schemarouter import SQLiteRunTraceStore, TraceRetentionPolicy

store = SQLiteRunTraceStore(
    "schemarouter-traces.sqlite3",
    retention_policy=TraceRetentionPolicy(
        max_age_seconds=30 * 24 * 60 * 60,
        max_runs=10_000,
    ),
)
```

보존 정책을 설정한 상태에서 `prune_on_terminal_append=True`(기본값)이면 종료 이벤트 추가와 보존 정책에 따른 정리를 하나의 SQLite 쓰기 트랜잭션으로 커밋합니다. `max_age_seconds`와 `max_runs`는 **완료된 실행 기록에만** 적용하며, 미완료 기록은 이 한도만으로 삭제하지 않습니다.

오래된 미완료 실행 기록의 정리는 별도 옵션인 `stale_incomplete_after_seconds`를 명시해야 활성화됩니다. 장애로 중단되거나 방치된 실행 기록이 삭제될 수 있으므로 합법적으로 실행될 수 있는 최장 시간보다 충분히 긴 임계값을 사용해야 합니다.

운영자는 결정론적 정리를 직접 호출할 수도 있습니다.

```python
result = store.prune(
    policy=TraceRetentionPolicy(max_runs=10_000),
)
print(result.deleted_runs, result.deleted_events)
```

SQLite 쓰기는 `BEGIN IMMEDIATE`로 직렬화합니다. 여러 `SQLiteRunTraceStore` 인스턴스가 같은 데이터베이스 파일을 사용해도 정리와 추가가 중간에 부분적으로 뒤섞이지 않습니다. 보존 정책용 인덱스는 종료 상태와 마지막 타임스탬프를 지원하므로 정리할 때마다 이벤트 문서를 역직렬화할 필요가 없습니다.

삭제는 SQLite의 논리적 삭제입니다. WAL을 활성화했을 때 정리 작업이 데이터베이스 또는 WAL 파일 크기를 즉시 줄인다고 보장할 수 없습니다. 파일 공간을 실제로 회수하려면 운영 상황에 맞춰 WAL을 checkpoint하고, 애플리케이션이 추적 저장소를 사용하지 않는 유지보수 시간에만 SQLite `VACUUM`을 실행하십시오. SchemaRouter는 정리 도중 자동으로 `VACUUM`을 실행하지 않습니다.

## 개인정보 보호

추적 저장소는 전달된 이벤트 envelope를 정확히 보존합니다. 런타임이 생성한 이벤트는 호출자가 명시적으로 원시 추적을 선택하지 않는 한, 저장소에 도달하기 **전에 구조적 민감 정보 가림 처리**를 거칩니다.

`RunConfig.metadata`는 신뢰할 수 있는 프로세스 내부 컨텍스트입니다. `include_payloads`와 무관하게 런타임 `RunEvent` envelope로 복사하지 않습니다. 따라서 테넌트 라우팅, 호스트 내부 연관관계 식별자, 상위 애플리케이션에서 필요한 자격 증명, 추적 데이터가 되면 안 되는 값을 담을 수 있습니다.

추적 기록에 보이는 메타데이터는 별도의 명시적 동의(opt-in)가 필요합니다.

```python
RunConfig(
    tags=["batch-import"],
    trace_metadata={"request_id": "req-123"},
)
```

`tags`는 필터링을 위한 구조화된 라벨로 이벤트에 유지됩니다. `trace_metadata`는 모든 이벤트에 중복 기록하지 않고 `run.start` 이벤트에만 작성합니다. 이전 버전에서 이후 이벤트에도 메타데이터를 기록했다면 해당 과거 추적 기록을 재생할 수 있습니다.

기본적으로 요청 및 도구 페이로드의 값은 완전히 생략합니다. 다음 설정을 활성화하면:

```python
RunConfig(include_payloads=True)
```

인자, 계획, 결과, 예외 메시지가 포함될 수 있습니다. 이 설정으로 `RunConfig.metadata`가 보이게 되는 것은 아닙니다. 페이로드 또는 `trace_metadata`에 있는 일반적인 자격 증명 키 및 지정한 민감 경로는 이벤트 발생·저장 전에 `[REDACTED]`로 교체됩니다. 키 이름에 의존한 휴리스틱 가림은 심층 방어 수단이며, `trace_metadata`에 민감 값을 아예 넣지 않아야 한다는 원칙을 대신하지 않습니다. 설정된 키·경로에서 발견한 비밀 값은 같은 실행의 후속 문자열 메시지에서도 제거합니다.

개인정보나 규제 대상 필드에는 `TraceRedactionConfig(sensitive_paths={...})`를 사용하십시오. 원시 데이터를 저장하려면 추가로 명시적 우회 옵션이 필요합니다.

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
    trace_metadata={"debug_context": "..."},
)
```

원시 추적은 페이로드와 명시적으로 노출하도록 선택한 추적 메타데이터를 그대로 보존할 수 있습니다. 이러한 데이터베이스는 민감한 애플리케이션 데이터로 취급하고 접근 제어, 저장 시 암호화, 백업, 보존 정책을 적용하십시오. SchemaRouter 자체는 SQLite 파일을 암호화하지 않습니다.

외부 생산자가 `SQLiteRunTraceStore.append()`를 직접 호출할 때는 자신의 `RunEvent` 객체를 직접 가려야 합니다. 저장소는 받은 envelope를 임의로 변형하지 않습니다.

## 외부 이벤트 스트림

영속화 헬퍼를 이용하면 호환되는 모든 비동기 `RunEvent` 스트림을 감쌀 수 있습니다.

```python
from schemarouter import record_run_events

async for event in record_run_events(source, store=store):
    consume(event)
```

따라서 저장 기능은 고수준 런타임 파사드에 종속되지 않습니다.

## 삭제와 수명주기

```python
store.delete(run_id)
store.close()
```

컨텍스트 매니저 사용도 지원합니다.

```python
with SQLiteRunTraceStore("traces.sqlite3") as store:
    ...
```

## 적용 범위

실행 추적 기록은 관측·감사를 위한 장치이며, 에이전트 제어 흐름을 재개하는 체크포인트 시스템이 아닙니다. 워크플로 체크포인트와 메모리는 LangGraph 또는 다른 오케스트레이션 계층이 계속 관리해야 합니다. SchemaRouter의 추적 기록 재생은 실행을 동반하지 않습니다.

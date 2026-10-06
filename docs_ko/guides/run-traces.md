# 영속 run trace

SchemaRouter는 tool call을 재실행하지 않고 audit/debug/replay할 수 있도록 typed `RunEvent` stream을 SQLite에 저장할 수 있습니다.

## Trace store 생성

```python
from schemarouter import SQLiteRunTraceStore
store = SQLiteRunTraceStore("schemarouter-traces.sqlite3")
```

표준 library `sqlite3`만 사용합니다.

## Runtime에서 직접 저장

`router.astream_events(request, trace_store=store)`로 event를 저장할 수 있습니다. 각 event는 downstream consumer에 yield되기 전에 기록되므로 persistence 실패를 조용히 무시해 unaudited execution history를 만들지 않습니다.

## 실행 없는 replay

`replay_run_events(store, run_id)`는 검증된 historical `RunEvent`만 읽으며 planner/executor/network/tool invoker를 호출하지 않습니다.

## Trace invariant

persisted run은 sequence 0의 `run.start`로 시작하고 하나의 immutable `run_id`, 연속 sequence, 단조 timestamp를 유지해야 합니다. 두 번째 `run.start`나 `run.end`/`run.error` 이후 event는 허용하지 않습니다. corrupt JSON, identity mismatch, gap, timestamp regression은 `TraceError`로 fail-closed됩니다. terminal event 전 process가 종료된 incomplete trace는 허용합니다.

## Privacy

Trace store는 전달받은 event envelope를 그대로 저장합니다. Runtime이 생성한 event는 caller가
raw tracing을 명시하지 않는 한 store에 도달하기 **전에** structured redaction을 거칩니다.

`RunConfig.metadata`는 trusted process-local context입니다. `include_payloads` 값과 무관하게
runtime `RunEvent` envelope로 복사되지 않습니다. Tenant routing, host 내부 correlation context,
주변 application code에서만 필요한 credential처럼 trace data가 되어서는 안 되는 값에 사용합니다.

Trace에 노출할 metadata는 별도로 명시해야 합니다.

```python
RunConfig(
    tags=["batch-import"],
    trace_metadata={"request_id": "req-123"},
)
```

`tags`는 filtering을 위한 structural label로 event에 유지됩니다. `trace_metadata`는 동일한
run metadata가 모든 event에 반복 저장되지 않도록 `run.start` event에 한 번만 기록됩니다.
과거 trace처럼 이후 event에도 metadata가 들어 있는 기록은 계속 replay할 수 있습니다.

기본값에서는 request/tool payload value를 포함하지 않습니다. 다음과 같이 payload tracing을 켜면:

```python
RunConfig(include_payloads=True)
```

argument, plan, result, exception message가 포함될 수 있습니다. 이 설정은
`RunConfig.metadata`를 trace에 노출시키지 않습니다. Payload 또는 `trace_metadata` 안의
일반적인 credential key와 설정된 sensitive path는 emission/persistence 전에 `[REDACTED]`로
대체됩니다. Heuristic key redaction은 defense in depth일 뿐이므로 민감한 값을
`trace_metadata`에 넣지 않는 원칙을 대체하지 않습니다. 설정된 key/path에서 발견된 secret
값은 같은 run의 이후 문자열 message에서도 제거됩니다.

Application-specific 개인정보나 규제 대상 field는
`TraceRedactionConfig(sensitive_paths={...})`로 지정할 수 있습니다. 원문 저장은 별도의
명시적 escape hatch가 필요합니다.

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
    trace_metadata={"debug_context": "..."},
)
```

Raw tracing은 payload와 명시적으로 opt-in한 trace metadata를 그대로 저장할 수 있습니다.
이런 DB는 민감 application data로 취급하고 적절한 access control, encryption-at-rest,
backup, retention policy를 적용해야 합니다. SchemaRouter 자체는 SQLite file을 암호화하지 않습니다.

외부 producer가 `SQLiteRunTraceStore.append()`를 직접 호출하는 경우에는 자신의
`RunEvent`를 직접 redact해야 합니다. Store는 event envelope를 의도적으로 수정하지 않습니다.

## 보존 정책과 pruning

기존 배포와의 호환성을 위해 retention은 opt-in입니다. 장기 실행 서비스에서는 명시적인
상한을 권장합니다.

```python
from schemarouter import TraceRetentionPolicy

store = SQLiteRunTraceStore(
    "schemarouter-traces.sqlite3",
    retention_policy=TraceRetentionPolicy(
        max_age_seconds=30 * 24 * 60 * 60,
        max_complete_runs=10_000,
    ),
)
```

기본 `automatic=True`에서는 모든 event마다가 아니라 `run.start`와 terminal event 같은 run
경계에서 pruning합니다. `max_age_seconds`는 완료 run의 마지막 event timestamp를 기준으로
TTL을 적용하고, `max_complete_runs`는 가장 최근에 완료된 run만 지정 개수만큼 유지합니다.
이 두 설정은 incomplete run을 삭제하지 않습니다.

Incomplete run을 정리하려면 `stale_incomplete_age_seconds`를 별도로 명시해야 합니다. 이 옵션을
켜면 cutoff보다 최근 event가 없는 incomplete run은 삭제 대상이 되므로 실제 active run의 최대
idle 시간보다 충분히 큰 값을 사용해야 합니다.

`store.prune()`으로 설정된 정책을 수동 실행할 수 있고, `policy=`로 일회성 정책을 전달할 수도
있습니다. Pruning은 하나의 `BEGIN IMMEDIATE` transaction에서 수행되므로 같은 SQLite file을
사용하는 여러 store instance의 append와 직렬화되며, event row는 foreign-key cascade로 함께
삭제됩니다.

삭제 후 SQLite file 크기가 즉시 줄어드는 것은 아닙니다. WAL mode에서는 삭제된 page가 DB/WAL
내에서 재사용될 수 있으며 checkpoint 전까지 파일이 남을 수 있습니다. `prune()`은 장시간
exclusive lock을 유발할 수 있는 `VACUUM`이나 truncating checkpoint를 자동 수행하지 않습니다.
실제 파일 축소가 필요하면 application traffic을 멈춘 maintenance window에서 checkpoint/VACUUM을
별도로 실행해야 합니다.

## 범위

run trace는 observability/audit 기능이며 agent control flow 재개를 위한 checkpoint system이 아닙니다. workflow checkpoint와 memory는 LangGraph 같은 orchestration layer가 담당합니다.

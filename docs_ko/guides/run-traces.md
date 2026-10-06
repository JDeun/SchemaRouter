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

기본값에서는 payload value 자체를 포함하지 않습니다. 다음과 같이 payload tracing을 켜면:

```python
RunConfig(include_payloads=True)
```

argument, plan, result, metadata, exception message가 포함될 수 있지만 일반적인 credential key와
설정된 sensitive path는 emission/persistence 전에 `[REDACTED]`로 대체됩니다. 해당 key/path
아래에서 발견된 secret 값은 같은 run의 이후 문자열 message에서도 제거됩니다.

Application-specific 개인정보나 규제 대상 field는
`TraceRedactionConfig(sensitive_paths={...})`로 지정할 수 있습니다. 원문 저장은 별도의
명시적 escape hatch가 필요합니다.

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
)
```

Raw tracing은 credential과 개인정보를 그대로 저장할 수 있습니다. 이런 DB는 민감
application data로 취급하고 적절한 access control, encryption-at-rest, backup, retention
policy를 적용해야 합니다. SchemaRouter 자체는 SQLite file을 암호화하지 않습니다.

외부 producer가 `SQLiteRunTraceStore.append()`를 직접 호출하는 경우에는 자신의
`RunEvent`를 직접 redact해야 합니다. Store는 event envelope를 의도적으로 수정하지 않습니다.

## 범위

run trace는 observability/audit 기능이며 agent control flow 재개를 위한 checkpoint system이 아닙니다. workflow checkpoint와 memory는 LangGraph 같은 orchestration layer가 담당합니다.

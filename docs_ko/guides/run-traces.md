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

기본 `astream_events()`는 argument value/result payload를 redact합니다. `RunConfig(include_payloads=True)`를 명시하면 argument, plan, result, exception message가 disk에 남을 수 있으므로 해당 DB를 민감 application data로 취급해야 합니다. SchemaRouter 자체는 SQLite file을 암호화하지 않습니다.

## 범위

run trace는 observability/audit 기능이며 agent control flow 재개를 위한 checkpoint system이 아닙니다. workflow checkpoint와 memory는 LangGraph 같은 orchestration layer가 담당합니다.

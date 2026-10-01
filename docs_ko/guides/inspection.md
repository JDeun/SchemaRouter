# 운영 상태 확인

SchemaRouter는 `SQLiteRegistry`로 capability catalog를, `SQLiteRunTraceStore`로 실행 event를
저장할 수 있습니다. `schemarouter inspect` 명령은 등록된 tool을 실행하지 않고 이 상태를
확인합니다.

확인할 수 있는 질문의 예:

- 어떤 API/tool이 등록되어 있는가?
- 어떤 endpoint가 만들어졌는가?
- read-only / mutating / destructive / unclassified인가?
- method/path/parameter/output field는 무엇인가?
- 어떤 source URL/adapter에서 왔는가?
- 현재 schema fingerprint와 binding 상태는 무엇인가?
- 어떤 run이 성공/실패했는가?

## Registry 확인

```bash
schemarouter inspect registry --db ./schemarouter-registry.sqlite3
```

예시 형태:

```text
Registry v3: 2 tools, 5 endpoints (4 read-only, 1 mutating, 0 unclassified)
- materials: 3 endpoints [9e8d12a6b487]
  - search: GET /materials · read-only · 2 params/6 fields [c77ac9d7181a]
```

Full SHA-256 fingerprint는 JSON 출력에서 확인할 수 있습니다.

## Tool 상세

```bash
schemarouter inspect tool materials --db ./schemarouter-registry.sqlite3
```

자동화용 JSON:

```bash
schemarouter inspect tool materials   --db ./schemarouter-registry.sqlite3   --json
```

## Run trace

```bash
schemarouter inspect traces --db ./schemarouter-traces.sqlite3
schemarouter inspect traces --db ./schemarouter-traces.sqlite3 --complete
schemarouter inspect trace <RUN_ID> --db ./schemarouter-traces.sqlite3
```

기본 redacted `RunConfig`로 저장한 payload는 inspection 단계에서 복구할 수 없습니다.
`include_payloads=True`로 저장했다면 SQLite DB 자체를 민감 데이터로 취급해야 합니다.

## Python API

```python
from schemarouter import SQLiteRegistry, inspect_registry

with SQLiteRegistry("registry.sqlite3") as registry:
    snapshot = inspect_registry(registry)

print(snapshot.tool_count)
print(snapshot.endpoint_count)
```

`inspect_registry`, `inspect_tool`, `inspect_trace`, `inspect_traces`를 제공합니다.

## Live router inspection

```python
router = SchemaRouter()
# ... register/import capabilities ...

snapshot = router.inspect()
print(snapshot.model_dump_json(indent=2))
```

Live view에는 analyzer, decision backend, decision policy, execution policy, bound tool,
cooldown 중인 access path, health monitor 상태 등이 포함됩니다.

Invoker object, credential, arbitrary metadata value, argument/result payload는 포함하지 않습니다.

## Static HTML dashboard

```bash
schemarouter dashboard   --registry ./schemarouter-registry.sqlite3   --traces ./schemarouter-traces.sqlite3   --output ./artifacts/schemarouter-dashboard.html
```

Dashboard는 self-contained static HTML입니다.

- 별도 server 불필요
- external JavaScript 없음
- analytics 없음
- tool execution button 없음
- credential 편집 없음
- raw trace payload rendering 없음

실제 예제:

```bash
python examples/inspection_dashboard.py
```

[Capability Explorer →](../getting-started/schema-explorer.md)

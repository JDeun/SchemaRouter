# 운영 상태 확인

SchemaRouter는 등록된 capability를 `SQLiteRegistry`에, 실행 기록을
`SQLiteRunTraceStore`에 저장할 수 있습니다. `schemarouter inspect`는 tool을 호출하지 않고
이 정보를 읽어 현재 상태를 보여 줍니다.

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

화면에는 짧은 fingerprint를 보여 주고, JSON 출력에는 전체 SHA-256 값을 담습니다.

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

기본 `RunConfig`는 payload 값을 가려서 저장합니다. 이렇게 저장된 값은 나중에 inspection으로
복원할 수 없습니다. `include_payloads=True`를 켰다면 SQLite 파일 자체에 민감한 값이 들어갈 수
있으므로 접근 권한을 별도로 관리해야 합니다.

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

`router.inspect()`는 analyzer, decision backend, 실행 정책, 현재 bound tool, cooldown 중인
access path, health monitor 상태를 함께 보여 줍니다.

Invoker 객체나 credential, 임의 metadata 값, 실제 argument/result payload는 이 출력에 넣지
않습니다.

## Static HTML dashboard

```bash
schemarouter dashboard   --registry ./schemarouter-registry.sqlite3   --traces ./schemarouter-traces.sqlite3   --output ./artifacts/schemarouter-dashboard.html
```

Dashboard는 파일 하나로 열 수 있는 정적 HTML입니다.

- 별도 server가 필요하지 않습니다.
- 외부 JavaScript를 불러오지 않습니다.
- analytics를 넣지 않습니다.
- tool 실행 버튼이나 credential 편집 기능이 없습니다.
- raw trace payload를 화면에 다시 노출하지 않습니다.

실제 예제:

```bash
python examples/inspection_dashboard.py
```

[Capability Explorer →](../getting-started/schema-explorer.md)


## Capability decision trace 확인

Decision trace는 host가 명시적으로 전달하는 observability record입니다. SchemaRouter가 자동으로 저장하지 않습니다.

```python
inspection = router.inspect(decision_traces=[trace])
```

Live inspection model은 visible capability ID, final disposition, normalized reason code만 compact summary로 노출합니다. Hidden capability, score/rank 값, payload, credential, private header, execution binding은 복원하지 않습니다.

직렬화된 trace는 직접 inspect할 수 있습니다.

```bash
schemarouter inspect decision-trace decision-trace.json --json
schemarouter inspect decision-trace decision-trace.json --detailed --json
```

Decision trace를 live `RouterInspection` 에 전달하면 HTML dashboard에도 compact decision-trace table이 추가됩니다. 전체 contract와 privacy 경계는 [Capability decision trace](capability-decision-traces.md)를 참고하세요.

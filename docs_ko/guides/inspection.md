# Operational inspection

SchemaRouter는 `SQLiteRegistry`로 registered capability catalog를, `SQLiteRunTraceStore`로 execution event stream을 persist할 수 있습니다. `schemarouter inspect`는 registered tool을 실행하지 않고 이 artifact를 노출합니다.

다음 질문에 답하기 위한 operational surface입니다.

- 현재 어떤 API/tool이 등록됐는가?
- 어떤 endpoint가 구성됐는가?
- read-only/mutating/destructive/unclassified 상태는 무엇인가?
- HTTP method/path, parameter, output field는 무엇인가?
- 어떤 source URL/adapter가 capability를 만들었는가?
- OpenAPI execution base URL이 bind됐고 external reference가 resolve됐는가?
- 각 tool/endpoint의 schema fingerprint는 무엇인가?
- 어떤 persisted run이 완료/실패했거나 endpoint를 사용했는가?

## Registry inspection

```bash
schemarouter inspect registry --db ./schemarouter-registry.sqlite3
```

예시:

```text
Registry v3: 2 tools, 5 endpoints (4 read-only, 1 mutating, 0 unclassified)
- materials: 3 endpoints [9e8d12a6b487]
  - search: GET /materials · read-only · 2 params/6 fields [c77ac9d7181a]
- experiments: 2 endpoints [93aaf450ac8c]
  - create: POST /experiments · mutating · 4 params/2 fields [ea179fd5cf2a]
```

축약 fingerprint는 display aid이며 JSON output은 전체 SHA-256을 포함합니다.

Python weather tool 예시:

```text
Registry v1: 1 tools, 1 endpoints (1 read-only, 0 mutating, 0 unclassified)
- current_weather: 1 endpoints [7c5d43e1f901]
  - current_weather: - - · read-only · 1 params/3 fields [f1d90a4c6b2e]
```

가능한 경우 allowlisted ingestion provenance인 `adapter`, `source_url`, resolved/approved OpenAPI URL, OPTIMADE versioned base URL, protocol/API version, execution-binding state, external-reference resolution count도 보여줍니다. Arbitrary metadata는 inspection view로 복사하지 않습니다.

## Tool 하나 상세 검사

```bash
schemarouter inspect tool materials --db ./schemarouter-registry.sqlite3
```

Endpoint classification, method/path, parameter, required/optional status, output field, projection path, full fingerprint를 확장해 보여줍니다.

Automation/dashboard용 JSON:

```bash
schemarouter inspect tool materials \
  --db ./schemarouter-registry.sqlite3 \
  --json
```

JSON에는 persisted ToolSpec document와 derived tool/endpoint fingerprint가 포함됩니다.

## Run trace 검사

```bash
schemarouter inspect traces --db ./schemarouter-traces.sqlite3
```

Machine-readable output은 `--json`을 사용합니다.


```bash
schemarouter inspect traces --db ./schemarouter-traces.sqlite3 --complete
schemarouter inspect traces --db ./schemarouter-traces.sqlite3 --incomplete
```

```bash
schemarouter inspect trace <RUN_ID> --db ./schemarouter-traces.sqlite3
```

## CLI가 하지 않는 것

Inspection은 execution과 분리됩니다.

- registered API 호출 안 함
- proposal approve 안 함
- invoker/credential bind 안 함
- execution policy 변경 안 함
- missing DB path에서 빈 DB를 만들지 않고 거부
- trace payload visibility는 application이 원래 persist한 범위로 제한

Default redacted `RunConfig`로 기록했다면 hidden argument/result payload를 복구할 수 없습니다. `include_payloads=True`로 persist한 SQLite DB는 그에 맞게 보호해야 합니다.

## Python inspection API

```python
from schemarouter import SQLiteRegistry, inspect_registry

with SQLiteRegistry("registry.sqlite3") as registry:
    snapshot = inspect_registry(registry)

print(snapshot.tool_count)
print(snapshot.endpoint_count)
```

Public helper에는 `inspect_registry`, `inspect_tool`, `inspect_trace`, `inspect_traces`가 있습니다.

## Live router inspection

Persistent SQLite는 저장된 상태를 보여줍니다. Running process는 실제 trusted invoker binding과 planner/policy configuration도 보고할 수 있습니다.

```python
router = SchemaRouter()
# ... register/import capabilities ...

snapshot = router.inspect()
print(snapshot.model_dump_json(indent=2))
```

Live view에는 analyzer class, configured decision-backend class, bounded decision policy, execution policy, actual bound tool key, availability cooldown 안의 access path, registered health-probe status/background monitor 상태가 추가됩니다.

Invoker object, credential, arbitrary metadata value, argument/result/payload value는 포함하지 않습니다.

대표 JSON:

```json
{
  "registry": {
    "version": 1,
    "tool_count": 1,
    "endpoint_count": 1,
    "read_only_endpoints": 1,
    "mutating_endpoints": 0,
    "unclassified_endpoints": 0
  },
  "planner": {
    "analyzer": "KeywordAnalyzer",
    "decision_backend": null,
    "decision_policy": {
      "enabled": false,
      "tool_selection": false,
      "endpoint_selection": false,
      "field_selection": false,
      "evidence_sufficiency": false,
      "fallback": "deterministic"
    }
  },
  "execution": {
    "policy": {
      "allow_mutations": false,
      "allow_destructive": false,
      "allow_unclassified_remote": false,
      "approval_mode": "never"
    },
    "bound_tools": ["current_weather"],
    "unavailable_access_paths": [],
    "health_monitor_running": false,
    "health_probes": []
  }
}
```

Full registry section에는 safe tool/endpoint inspection record와 fingerprint도 있습니다. Health probe callable 자체는 serialize하지 않으며 availability는 live process state라 persisted registry만으로 재구성하지 않습니다.

## Dashboard export

0.6 개발 계열부터 동일한 읽기 전용 inspection model을 별도의 서버가 필요 없는 단일 HTML 문서로 렌더링할 수 있습니다.

```bash
schemarouter dashboard \
  --registry ./schemarouter-registry.sqlite3 \
  --traces ./schemarouter-traces.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

Trace DB는 optional입니다.

```bash
schemarouter dashboard \
  --registry ./schemarouter-registry.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

Dashboard에는 capability count, adapter/source provenance, endpoint method/path와 side-effect classification, schema fingerprint, persisted binding state, recent run summary, error count가 있으며 capability table은 browser에서 filter할 수 있습니다.

Static export이므로 server dependency/external JavaScript/analytics/tool execution button/credential editing/raw trace payload rendering이 없습니다. Application은 typed inspection model로 `render_dashboard(...)` 또는 `write_dashboard(...)`를 직접 호출할 수 있습니다.

### Dashboard preview

Checked-in preview는 generated dashboard와 같은 layout/interaction model을 사용하며 demo data만 포함합니다.

<iframe
  src="/SchemaRouter/assets/inspection-dashboard-preview.html"
  title="SchemaRouter inspection dashboard preview"
  style="width: 100%; height: 720px; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 12px;"
></iframe>

[별도 페이지에서 dashboard preview 열기](/SchemaRouter/assets/inspection-dashboard-preview.html)

### End-to-end example

```bash
python examples/inspection_dashboard.py
```

Default output:

```text
artifacts/inspection-demo/registry.sqlite3
artifacts/inspection-demo/traces.sqlite3
artifacts/inspection-demo/dashboard.html
```

Path override:

```bash
python examples/inspection_dashboard.py \
  --registry /tmp/registry.sqlite3 \
  --traces /tmp/traces.sqlite3 \
  --output /tmp/schemarouter-dashboard.html
```

Architecture:

```text
SQLiteRegistry / SQLiteRunTraceStore       live SchemaRouter
              |                                  |
        inspection API ------------------- inspect_router()
         /           \
       CLI       static dashboard
```

Future TUI/long-running web console도 SQLite table을 직접 query하지 말고 동일 inspection contract를 사용해야 합니다.

## Capability decision trace 검사

Decision trace는 explicit host-provided observability record이며 SchemaRouter가 자동 persist하지 않습니다.

```python
inspection = router.inspect(decision_traces=[trace])
```

Live inspection model은 visible capability ID, final disposition, normalized reason code의 compact candidate summary만 노출합니다. Hidden capability, score/rank, payload, credential, private header, execution binding은 재구성하지 않습니다.

Serialized trace:

```bash
schemarouter inspect decision-trace decision-trace.json --json
schemarouter inspect decision-trace decision-trace.json --detailed --json
```

Live `RouterInspection`에 decision trace를 제공하면 HTML dashboard가 compact decision-trace table을 추가합니다. 전체 contract/privacy boundary는 [Capability decision traces](capability-decision-traces.md)를 참고하십시오.

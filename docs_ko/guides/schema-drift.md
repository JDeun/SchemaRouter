# Schema drift와 compatibility

SchemaRouter는 stale plan과 stale invoker binding을 exact fingerprint로 reject합니다. Compatibility analysis는 diagnostic일 뿐입니다. 두 trusted schema snapshot이 왜 다른지 설명하지만 old plan이 new contract에서 실행되도록 허용하지 않습니다.

## Endpoint snapshot 비교

```python
from schemarouter import compare_endpoint_specs
report = compare_endpoint_specs(previous_endpoint, current_endpoint)
print(report.compatibility)
for change in report.changes:
    print(change.severity, change.path, change.kind)
```

Compatibility:

- `identical` — executable contract fingerprint 동일
- `compatible` — conservatively additive/widening으로 증명 가능한 change만
- `breaking` — caller/projection을 invalidate할 수 있는 contract change
- `security_review` — side-effect/destructive semantics 변경, local authority review 필요

Arbitrary JSON Schema compatibility는 증명하기 어렵기 때문에 unknown change는 safe라고 추측하지 않고 breaking으로 분류합니다.

## Complete tool 비교

```python
from schemarouter import compare_tool_specs
report = compare_tool_specs(previous_tool, current_tool)
```

Endpoint addition/removal, endpoint contract change, source type/license 같은 evidence metadata, fingerprint change를 설명할 ordering change를 포함합니다.

## Persisted registry 간 CLI inspection

SQLite registry의 old/current snapshot을 tool 실행 없이 비교:

```bash
schemarouter inspect diff materials \
  --old-db registry-before.sqlite3 \
  --new-db registry-current.sqlite3
```

Endpoint 하나 또는 JSON:

```bash
schemarouter inspect diff materials \
  --endpoint search \
  --old-db registry-before.sqlite3 \
  --new-db registry-current.sqlite3 \
  --json
```

CLI는 validated `ToolSpec` snapshot을 load해 Python API와 같은 conservative comparison을 실행합니다. Tool register/bind/invoke를 하지 않습니다. SQLite connection은 normal registry implementation을 사용하므로 filesystem-level read-only claim이 아니라 execution-safe inspection path입니다.

## HTTP validator optimization

GET-backed schema source는 refresh 중 authoritative HTTP validator를 재사용할 수 있습니다. Privacy-safe validator value만 저장하며 authentication header는 저장하지 않습니다.

- `ETag` -> `If-None-Match`
- `Last-Modified` -> `If-Modified-Since`
- `304 Not Modified` -> registry write 없이 즉시 `unchanged`

Validator metadata는 canonical tool fingerprint에서 제외됩니다. Updated validator는 trusted loader cache에도 있을 수 있어 unchanged schema가 새 ETag 기억만을 위해 registry version을 올릴 필요가 없습니다.

Correctness는 HTTP validator에 의존하지 않습니다. Provider가 validator를 주지 않거나 무시하거나 new document를 반환하면 full fetch, fingerprint comparison, compatibility classification, CAS apply path로 돌아갑니다.

한 conditional GET이 complete inspected document unchanged를 증명할 수 있는 schema surface로 제한합니다.

| Source | Conditional refresh |
| --- | --- |
| OpenAPI without external refs | ETag / Last-Modified |
| OpenRPC document | ETag / Last-Modified |
| OData `$metadata` | ETag / Last-Modified |
| OpenAPI with external refs | full fetch; root validator 불충분 |
| OPTIMADE | full multi-resource fetch; `/info`만으로 불충분 |
| GraphQL introspection | full introspection POST |
| MCP | transport-specific refresh |

`If-None-Match`, `If-Modified-Since`는 refresh의 accepted-schema validator state용으로 예약됩니다. Caller-supplied 값은 conditional request 전에 제거하고 unrelated trusted schema header는 보존합니다. Arbitrary external condition이 current registered snapshot과 무관한 304를 만들지 못하게 합니다.

## Registered provider reinspect

URL-backed OpenAPI/MCP/OPTIMADE/GraphQL/OData/OpenRPC tool을 candidate commit 전에 reinspect할 수 있습니다. `add_mcp_stdio()`, `add_mcp_client_factory()` MCP도 exact process-local trusted binding이 current인 동안 refresh 가능합니다.

```python
result = await router.arefresh_schema("materials")
print(result.action)
print(result.report.compatibility)
```

One-shot policy:

- `identical` -> no registry write
- `compatible` -> default atomic apply
- `breaking` / `security_review` -> `pending_review`, unapplied

`apply_compatible=False`로 compatible도 report-only 가능:

```python
result = await router.arefresh_schema("materials", apply_compatible=False)
```

Schema/runtime auth material은 persist하지 않습니다. URL provider가 header를 요구하면 trusted `schema_headers`/`trusted_headers`를 refresh 때 다시 전달합니다. Stdio/transport-neutral MCP는 current fingerprint-matched process-local `MCPBoundInvoker` factory만 재사용합니다. Factory, credential, subprocess config, transport state는 `ToolSpec`/watcher snapshot에 복사하지 않습니다. Binding이 missing/stale이면 source provenance를 fabricate하지 않고 fail closed합니다.

Apply는 비교한 exact registry version/tool fingerprint를 사용합니다. Remote inspection 중 다른 writer가 registry를 mutate하면 CAS가 실패하여 unseen newer snapshot 위에 candidate를 적용하지 않습니다.

## Native database schema refresh

Native onboarding API로 등록한 caller-owned relational/vector/graph/record-store backend는 process-local re-introspection callback을 유지합니다. Backend client/credential/connection pool/transport state는 ToolSpec metadata에 persist하지 않습니다.

```python
result = await router.arefresh_native_schema("warehouse.orders")
```

동일 conservative policy를 적용합니다. Identical은 unchanged, proven-compatible drift는 atomic apply/rebind 가능, breaking drift는 current executable contract를 유지하면서 `pending_review`로 quarantine합니다. `aaccept_native_schema_pending(...)`으로 explicit acceptance 가능합니다.

Long-lived process:

```python
await router.start_native_schema_watcher(interval_seconds=300)
# ...
await router.stop_native_schema_watcher()
```

One-shot `check_native_schema_watches_once()`도 있습니다. Watcher는 process-local이며 restart 후 caller-owned backend onboarding이 다시 필요합니다.

## Periodic schema watcher

```python
router.register_schema_watch(
    "materials",
    interval_seconds=300,
    apply_compatible=True,
    schema_headers={"Authorization": f"Bearer {schema_token}"},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)
await router.start_schema_watcher(max_concurrency=4)
```

각 due check는 one-shot refresh boundary를 재사용하며 `compare_tool_specs()`, fingerprint check, CAS replacement를 우회하지 않습니다.

Default:

- identical -> `unchanged`
- proven-compatible -> `apply_compatible=True`면 atomic apply
- compatible + false -> `report_only`
- breaking/security -> current contract 유지 + `pending_review`
- transport/schema error -> `error`, next interval retry
- removed/unrefreshable -> `stale`

Credential 노출 없이 inspect:

```python
for watch in router.schema_watch_snapshots():
    print(watch.tool, watch.status, watch.last_compatibility, watch.pending_change_count)

pending = router.schema_watch_pending_review("materials")
if pending is not None:
    for change in pending.report.changes:
        print(change.severity, change.path, change.kind)
```

`router.inspect()`도 watcher state를 보고합니다. Header value, client factory, trusted transport state는 snapshot에 나타나지 않습니다.

On-demand 전체 check:

```python
await router.check_schema_watches_once()
```

Stop:

```python
await router.stop_schema_watcher()
```

Interval은 tool별입니다. Overlapping cycle을 serialize하고 refresh concurrency를 bound하여 slow provider가 unbounded duplicate write를 만들지 않게 합니다.

ETag/Last-Modified conditional request는 optimization일 뿐이며 fetched candidate는 replacement 전 항상 fingerprint/compare됩니다.

## Security-semantic drift

```text
GET -> POST / PUT / PATCH / DELETE
read_only: True -> False
destructive: False -> True
```

이런 변경은 ordinary compatibility가 아니라 `security_review`입니다. Remote description은 transition을 authorize하지 않으며 application이 trusted local policy 아래 re-import/review/rebind해야 합니다.

## 중요: compatible은 executable이라는 뜻이 아님

다음은 여전히 invalid입니다.

```text
old plan fingerprint
        !=
current endpoint fingerprint
        -> SchemaDriftError
```

`compare_endpoint_specs(...).compatibility == "compatible"`이어도 old plan은 replan하고 stale binding은 rebind해야 합니다. Report는 review/migration tooling/observability/CI용이지 execution check 우회용이 아닙니다.

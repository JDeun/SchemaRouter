# Capability graph drift

SchemaRouter는 이전에 컴파일한 capability contract 스냅샷과 새로 갱신한 스냅샷을 비교하여 capability graph에서 다시 컴파일해야 하는 노드를 식별할 수 있습니다.

```python
from schemarouter import compare_capability_graph_snapshot

report = compare_capability_graph_snapshot(graph, previous_contracts, refreshed_contracts)
if report.changed:
    print(report.compatibility)
    print(report.invalidated_capability_ids)
```

비교 결과는 결정적입니다. Capability contract fingerprint는 canonical JSON의 SHA-256 digest이므로 mapping 삽입 순서가 달라도 fingerprint는 변하지 않습니다.

## Invalidation 경계

변경되거나 제거된 contract는 breaking drift로 취급하며 해당 capability와 기존의 직접 predecessor/successor를 무효화합니다. 새 capability 추가는 compatible additive drift이며 새 노드만 재계산 대상으로 표시합니다.

이 API는 **invalidation metadata만 생성**합니다. Capability 실행, invocation migration, authorization 확대, host execution policy 대체를 수행하지 않습니다. Provider 수준의 OpenAPI, MCP, scientific-provider schema 변경은 기존 ToolSpec/schema-diff 계층에서 먼저 정규화하고, capability graph drift는 그 결과로 생성된 provider-neutral capability contract를 비교합니다. Runtime health는 별도 overlay이며 결정적 contract fingerprint에 포함되지 않습니다.

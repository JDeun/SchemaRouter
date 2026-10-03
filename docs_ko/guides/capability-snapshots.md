# Versioned capability graph snapshot

Capability graph snapshot은 immutable routing-contract state를 mutable runtime health와 분리하여 기록합니다.

```python
from schemarouter import create_capability_graph_snapshot, require_capability_snapshot

snapshot = create_capability_graph_snapshot(
    graph,
    contracts,
    source_schema_fingerprints={"provider": "..."},
    build_metadata={"builder": "ci"},
)
require_capability_snapshot(snapshot, requested_snapshot_id)
```

Snapshot ID는 canonical graph, contract, source-schema fingerprint 데이터의 SHA-256 digest입니다. Capability와 edge 순서는 정규화됩니다. Informational build metadata는 보존하지만 identity에서는 제외하므로 동일한 routing contract를 다른 환경에서 컴파일해도 재현 가능한 ID를 얻습니다.

`compare_capability_snapshots()`는 추가, 제거, 변경된 capability ID를 보고합니다. Host는 `require_capability_snapshot()`으로 retrieval/runtime 작업을 정확한 snapshot에 고정할 수 있으며 mismatch는 fail closed합니다.

Live provider health는 의도적으로 제외됩니다. Snapshot은 routing contract가 무엇이었는지를 기록할 뿐 현재 provider health를 고정하지 않습니다. SchemaRouter는 deploy, rollback, execution 또는 stale breaking schema의 묵시적 수용을 수행하지 않습니다.

# Versioned capability graph snapshots

Capability graph snapshot은 graph를 만들 때 사용한 provider-neutral contract와 source schema revision을 고정합니다. SHA-256 identity는 결정적이며 contract/source 순서와 관측용 build time은 digest에 영향을 주지 않습니다.

```python
from schemarouter import build_capability_snapshot, require_snapshot

snapshot = build_capability_snapshot(contracts, sources=source_revisions)
require_snapshot(requested_snapshot_id, snapshot)
graph = snapshot.build_graph()
```

Pinned request의 snapshot ID가 현재 로드된 graph revision과 다르면 fail-closed합니다. `compare_capability_snapshots()`는 추가·제거·변경된 capability ID를 식별하여 drift 이후 controlled successor snapshot을 만들 수 있게 합니다.

## Immutable state와 mutable state

Contract, provider/schema revision reference, builder identity는 immutable snapshot에 속합니다. Runtime health는 포함하지 않으며 routing 시점에 평가하는 mutable overlay입니다. 따라서 snapshot은 provider가 영원히 healthy하다고 가정하지 않으면서 reproducibility를 제공합니다. SchemaRouter는 snapshot을 배포·rollback·실행하지 않으며 lifecycle 결정은 host 책임입니다.

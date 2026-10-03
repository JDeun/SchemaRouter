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


## Atomic successor publication

장시간 실행되는 프로세스는 `CapabilitySnapshotStore` 로 하나의 검증된 snapshot과 dependency graph를 active 상태로 유지할 수 있습니다.

```python
from schemarouter import CapabilitySnapshotStore

store = CapabilitySnapshotStore.from_contracts(
    contracts,
    sources=source_revisions,
)

current = store.read()

published = store.compare_and_publish(
    refreshed_contracts,
    sources=refreshed_source_revisions,
    expected_revision=current.publication_revision,
    expected_snapshot_id=current.snapshot.snapshot_id,
)
```

Publication은 process-local serialized compare-and-swap 경계를 사용합니다. 기존 graph와 고정된 compatibility context를 기준으로 안전성이 보장되면 successor graph를 incremental하게 재구성하고, incremental correctness를 보장할 수 없으면 full rebuild로 전환합니다. 완성된 candidate publication 전체를 검증한 뒤 하나의 atomic reference replacement로 교체합니다.

Validation 실패, stale CAS precondition, rebuild 오류가 발생하면 predecessor publication은 그대로 유지됩니다. 따라서 reader는 이전의 완전한 publication 또는 새로운 완전한 publication만 보며 중간 상태의 graph를 관측하지 않습니다.

`CapabilitySnapshotPublication.provenance` 는 predecessor/successor snapshot ID와 source revision을 기록합니다. Runtime health는 immutable snapshot과 publication identity에 포함되지 않습니다. 따라서 health 재확인만으로 snapshot digest나 publication revision이 바뀌지 않습니다.

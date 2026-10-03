# Portable capability graph artifacts

SchemaRouter capability artifact는 컴파일된 capability contract를 환경 사이에서 이동하기 위한 결정적 JSON 문서입니다. Format version, graph digest, typed capability contract, source schema fingerprint, optional dependency metadata, non-secret provenance를 담습니다.

```python
from schemarouter import (
    build_capability_artifact,
    load_capability_artifact,
    serialize_capability_artifact,
)

artifact = build_capability_artifact(
    graph_digest=snapshot_id,
    capabilities=contracts,
    sources=sources,
)
document = serialize_capability_artifact(artifact)
loaded = load_capability_artifact(document)
```

현재 artifact format은 **1.1**입니다. SchemaRouter는 과거 **1.0** format도 읽고 deterministic migration을 수행한 뒤 반환합니다. 알 수 없는 새 버전은 fail-closed합니다.

## 1.0에서 1.1로 migration

1.1에서는 edge provenance를 `origin = "derived" | "external"` 로 명시합니다.

1.0 builder는 caller가 제공한 edge metadata를 받을 수 있었고, 그 edge가 포함된 contract로부터 다시 계산된 것인지 기록하지 않았습니다. 따라서 migration은 1.0 edge를 `external` 로 분류합니다. 더 강한 derived semantics를 임의로 만들어내지 않습니다.

```python
from schemarouter import migrate_capability_artifact

result = migrate_capability_artifact(old_document)

assert result.migration.from_format == "1.0"
assert result.migration.to_format == "1.1"
```

Migration은 변환 전에 source artifact digest를 검증하고 source digest를 non-secret migration provenance에 기록합니다. 현재 format에 migration을 다시 실행하면 idempotent하게 동작합니다.

## Semantic integrity

`validate_capability_artifact(...)` 는 중복 capability/source/edge identity와 dangling/self edge를 거부합니다.

완전히 derived된 artifact는 `build_capability_artifact_from_graph(...)` 로 생성할 수 있습니다. Derived edge는 포함된 capability contract와 다시 비교되고 canonical graph digest도 검증됩니다. External edge metadata를 실행 권한으로 승격하지 않습니다.

## CLI

```bash
schemarouter artifact inspect graph.json --json
schemarouter artifact migrate graph.json --json
```

Migration은 기본적으로 새 `.migrated.json` 파일을 만듭니다. `--overwrite` 를 명시하지 않으면 source 또는 기존 destination을 덮어쓰지 않습니다.

Artifact에는 credential과 live health/runtime state를 넣지 않습니다. Host는 CI에서 artifact를 compile/validate하고 자체 infrastructure로 배포한 뒤 load 이후 live health overlay를 적용할 수 있습니다. SchemaRouter는 artifact registry, signing service, deployment controller를 구현하지 않습니다.

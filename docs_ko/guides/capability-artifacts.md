# Portable capability graph artifacts

SchemaRouter capability artifact는 컴파일된 capability contract를 환경 사이에서 이동하기 위한 결정적 JSON 문서입니다. Format version, graph digest, typed capability contract, source schema fingerprint, optional dependency metadata, non-secret provenance를 담습니다.

```python
from schemarouter import build_capability_artifact, serialize_capability_artifact, load_capability_artifact

artifact = build_capability_artifact(graph_digest=snapshot_id, capabilities=contracts, sources=sources)
document = serialize_capability_artifact(artifact)
loaded = load_capability_artifact(document)
```

Load는 strict합니다. 지원하지 않는 format version과 digest mismatch는 fail-closed합니다. `1.0`이 초기 contract이며 reader는 알 수 없는 major format을 임의로 호환 처리하지 않습니다.

Artifact에는 credential과 live health/runtime state를 넣지 않습니다. Host는 CI에서 artifact를 compile/validate하고 자체 infrastructure로 배포한 뒤 load 이후 live health overlay를 적용할 수 있습니다. SchemaRouter는 artifact registry, signing service, deployment controller를 구현하지 않습니다.

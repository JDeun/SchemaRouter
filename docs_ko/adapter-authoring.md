# Adapter 작성

Adapter는 structured capability source를 SchemaRouter의 canonical contract로 연결합니다. core planner, registry, policy, executor를 protocol별로 분기시키지 않는 것이 원칙입니다.

`SourceAdapter`는 안정적인 `kind`, discovery priority, async `load()`를 제공하며 auto discovery에서 인식하지 못한 source에는 `None`, 지원하는 source에는 `AdapterLoadResult(tool=..., invoker=...)`를 반환합니다. passive GET/HEAD schema read만 기본 auto discovery 대상이며 GraphQL introspection POST, MCP handshake 같은 active probe는 명시적 opt-in이 필요합니다. refresh/watch도 `RefreshProfile`로 별도 선언해야 합니다.

Adapter는 `ToolSpec`, `EndpointSpec`, parameter/field contract, 가능한 경우 full input/output JSON Schema를 보존해야 합니다. remote capability는 `remote=True`, 실행 의미를 바꾸는 trusted 값은 fingerprint 대상인 `execution_metadata`에 둡니다. credential은 metadata나 model-visible argument에 넣지 않습니다.

일반 invoker는 `(endpoint_name, arguments)` contract를 사용하고 server-side field selection이 필요한 protocol은 전체 `ToolCall`을 받는 call-aware invoker를 사용할 수 있습니다. 어떤 경우에도 remote annotation을 mutation authority로 바꾸거나 validation/policy를 우회해서는 안 됩니다.

field contract는 datatype/shape, path/result_path, source가 명시한 unit, identifier/source type을 충실히 보존합니다. array item은 authoritative schema가 array임을 선언할 때만 `"*"` path를 사용하며 record alignment를 유지합니다. semantic ID, unit normalization, qualifier, licence는 authoritative structured source 또는 trusted local enrichment에서만 가져옵니다.

서드파티 adapter는 `schemarouter.adapters` entry point로 배포할 수 있지만 자동 import되지 않으며 application이 allowlist로 명시적으로 로드합니다. 새 adapter는 discovery, collision, fingerprint drift, validation, stale binding, credential separation, side-effect policy, projection, unit/qualifier fidelity, redirect/origin behavior를 conformance test로 검증해야 합니다.

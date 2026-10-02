# Stable core contract

SchemaRouter의 현재 product architecture는 research가 독립적으로 계속되는 동안 freeze할 수 있을 만큼 완성된 것으로 봅니다. 이는 1.0 API guarantee가 아니며 pre-1.0 compatibility policy는 [Versioning](versioning.md)을 따릅니다.

## 고정된 product boundary

```mermaid
flowchart TD
    S["Python / OpenAPI / MCP / OPTIMADE / adapter plugins"] --> R["typed registry"]
    R --> B["bounded capability retrieval"]
    B --> A["agent / application"]
    A --> P["planning/calls"]
    P --> V["validation + local execution policy"]
    V --> E["bound execution"]
```

retrieval은 execution authority가 아닙니다. `retrieve`/`aretrieve`는 registered contract에서 bounded typed candidate를 반환할 뿐 실행/권한을 부여하지 않습니다. executable variant도 current binding readiness를 추가로 filter할 뿐 side effect를 authorize하지 않습니다.

`CapabilityCandidate`는 route/tool/endpoint identity, effective input/output JSON Schema, parameter/output field, semantic ID/datatype/unit/qualifier, read/write/destructive classification, provider/source/access metadata, fingerprint를 보존합니다.

실제 invocation은 identity, schema/fingerprint, binding readiness, execution policy, approval, retry restriction, budget, trusted hook/transport를 계속 통과해야 합니다. external agent/framework/ranking이 authority를 부여할 수 없습니다.

LangChain/LangGraph/LlamaIndex는 optional adapter이지 alternate runtime이 아니며 core package는 optional dependency 없이 import/use 가능해야 합니다.

research는 같은 public facade 뒤에서 alternate retrieval index/representation, future K, adaptive shortlist, corrective re-retrieval, scoring backend, performance optimization, optional adapter 등을 시험할 수 있습니다.

public-boundary redesign은 reproducible correctness/security flaw, 기존 facade로 표현 불가능한 중요한 workflow, adapter로 해결할 수 없는 ecosystem constraint, 명시적 breaking minor release 같은 근거가 필요합니다. benchmark 개선만으로 facade를 재설계하지 않습니다.

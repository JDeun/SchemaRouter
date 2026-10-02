# 공개 로드맵

이 roadmap은 contributor가 변경 가능한 경계를 이해할 수 있도록 **stable product**, **research**, **ecosystem integration**, **community growth**를 분리합니다. 날짜 약속이 아니라 coordination view이며 현재 작업과 acceptance criterion의 source of truth는 GitHub issue입니다.

## Stable product

stable core는 typed capability retrieval과 schema-aware execution boundary입니다. local execution authority, schema/fingerprint validation, explicit side-effect policy, protocol-neutral contract를 보존해야 합니다. provider 하나를 지원하기 위해 core architecture를 다시 열지 말고 adapter, trusted SDK binding, framework bridge, decision plugin을 우선합니다.

## Research

research는 product default가 아닌 대안을 시험할 수 있습니다. frozen workload/split/promotion gate/negative result/history는 product 변경에 맞추기 위해 다시 쓰지 않습니다. 새 hypothesis에는 새 versioned experiment가 필요합니다.

## Ecosystem과 integration

목표는 기존 agent/tool ecosystem을 대체하는 것이 아니라 함께 사용할 수 있게 하는 것입니다. LangChain/LangGraph/LlamaIndex bridge, MCP/OpenAPI/OPTIMADE/GraphQL/OData/OpenRPC/HTTP-JSON, System One/Jev/Laya/Ollama, OpenTelemetry, third-party entry point를 optional하게 유지하며 SchemaRouter execution validation/policy를 우회하지 않습니다.

## Community와 adoption

발견·시험·검증·기여·도입을 쉽게 만드는 작업입니다. star는 lagging signal이며 vanity promotion보다 reproducible example, downstream integration, external reproduction, repeat usage를 우선합니다.

외부 contributor에게 적합한 작업은 bounded structured adapter, focused compatibility test, reproducible docs/example, finite-option decision plugin, authority를 보존하는 framework bridge, machine-readable benchmark reproduction, 명확한 failing test가 있는 reliability/DX defect입니다.

execution-authority semantics, destructive policy, persisted compatibility, frozen research workload/gate, release credential trust, general agent runtime 전환은 maintainer design이 먼저 필요합니다.

GitHub Discussions는 현재 의도적으로 보류하고 하나의 actionable issue queue를 유지합니다.

# SchemaRouter란?

SchemaRouter는 MCP, OpenAPI, Python, framework tool을 아우르는 **LLM/RAG 에이전트용 typed
capability retrieval 및 schema-aware execution 계층**입니다.

범용 agent framework보다는 범위가 좁고, 단순 semantic tool router보다는 더 깊은 실행 경계를
다룹니다. RAG에서 외부 정보가 API나 tool을 통해 들어오는 경우, SchemaRouter는 그 source를
typed endpoint/field contract로 정규화하고 상위 agent가 사용할 수 있는 작은 trusted executable
surface를 제공합니다.

## 역할 분리

| 계층 | 책임 |
| --- | --- |
| 애플리케이션 / agent framework | 대화, agent loop, graph, model strategy, memory, checkpoint |
| SchemaRouter | typed tool/endpoint planning, schema identity, validation, policy, execution boundary |
| Optional decision backend | 로컬에서 허가된 유한 후보 중 bounded selection |
| Capability source | OpenAPI, MCP, OPTIMADE, Python callable, 승인된 adapter/plugin |

Laya, Ollama, Jev 같은 decision backend는 중첩 agent가 아닙니다. 새 capability를 만들거나,
별도의 tool loop를 시작하거나, execution authority를 얻을 수 없습니다.

## 단순 라우팅보다 더 세분화된 계획

일반 router:

```text
Query -> Tool
```

SchemaRouter:

```text
Query
  -> semantic data need
  -> required response fields
  -> provider / access path
  -> tool / endpoint
  -> parameters
  -> evidence requirements
  -> schema + tool fingerprints
  -> execution policy / availability
```

계획은 실행 직전에 다시 검증됩니다.

## Endpoint가 first-class인 이유

하나의 API나 MCP server에는 여러 operation이 있을 수 있습니다. 서버 전체를 하나의 tool로
보면 다음 차이를 잃습니다.

- read와 mutation
- search와 detail
- required parameter 차이
- output schema 차이

그래서 SchemaRouter는 `EndpointSpec`을 first-class contract로 다룹니다.

## Field가 중요한 이유

질문에 필요하지 않은 field까지 모두 가져오면 bandwidth, latency, parsing, downstream context,
prompt token을 낭비할 수 있습니다. SchemaRouter는 **field-first, route-second** 원칙을 사용합니다.

1. 논리적으로 필요한 field를 정합니다.
2. 그 field를 제공할 수 있는 route를 찾습니다.
3. 가능하면 server-side projection을 사용합니다.
4. raw response를 검증합니다.
5. 최종적으로 필요한 field만 `ToolResult`에 남깁니다.

모호한 경우에는 지나친 pruning보다 recall을 우선합니다.

## 실행 단계에서 다시 검증하는 이유

Planning 결과 자체에는 실행 권한이 없습니다. planning과 execution 사이에 schema, binding,
parameter, policy가 바뀔 수 있습니다. Executor는 다음을 다시 확인합니다.

- required arguments
- schema/tool fingerprint
- local binding readiness
- execution policy / approval
- input schema
- trusted transport
- raw output schema
- field projection

## 하지 않는 것

SchemaRouter는 다음을 소유하려 하지 않습니다.

- chat message abstraction
- prompt-template ecosystem
- model-provider client
- conversation memory
- graph orchestration
- checkpointing

이 기능은 LangChain/LangGraph/LlamaIndex 또는 애플리케이션 계층에 남겨 둡니다.

[Capability retrieval 자세히 보기 →](capability-catalog.md) ·
[Field-first execution →](field-first-execution.md)

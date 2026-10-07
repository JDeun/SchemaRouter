# SchemaRouter란?

SchemaRouter는 MCP, OpenAPI, Python, 프레임워크 도구를 **하나의 타입 기반 capability
검색·실행 경계**로 다루는 라이브러리입니다.

범용 agent framework처럼 대화와 추론 루프 전체를 맡지는 않습니다. 대신 API나 tool에서 외부
데이터를 가져와야 할 때, 각 source를 endpoint/field 계약으로 정리하고 상위 agent가 볼 수 있는
실행 후보를 필요한 범위로 줄여 줍니다.

## 역할 분리

| 계층 | 책임 |
| --- | --- |
| 애플리케이션 / agent framework | 대화, agent loop, graph, model strategy, memory, checkpoint |
| SchemaRouter | typed tool/endpoint planning, schema identity, validation, policy, execution boundary |
| Optional decision backend | 로컬에서 허가된 유한 후보 중 bounded selection |
| Capability source | OpenAPI, MCP, OPTIMADE, Python callable, 승인된 adapter/plugin |

Laya, Ollama, Jev 같은 decision backend는 후보 선택을 보조할 뿐입니다. 새 capability를
만들거나 별도의 tool loop를 시작할 수 없고, 실행 권한도 갖지 않습니다.

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

이 계획은 그대로 실행하지 않고, 실제 호출 직전에 다시 검증합니다.

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

계획 결과만으로는 도구를 실행할 수 없습니다. 계획을 만든 뒤 실제 호출까지 사이에 schema,
binding, parameter, policy가 달라질 수 있기 때문에 executor가 다음 항목을 다시 확인합니다.

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

[Capability catalog 자세히 보기 →](capability-catalog.md) ·
[Field-first execution →](field-first-execution.md)

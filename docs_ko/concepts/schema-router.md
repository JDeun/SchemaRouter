# SchemaRouter란?

SchemaRouter는 **API, tool, data system 전반에서 AI agent를 위한 typed capability routing 및 governed execution layer**입니다.

범용 agent framework보다 역할은 좁고 semantic tool router보다 깊습니다. **Retrieval-Augmented Generation(RAG)**은 external source에서 가져온 정보로 generation을 보강합니다. 그 source가 API나 tool일 때 SchemaRouter는 retrieval/execution boundary의 일부를 담당할 수 있습니다. Source를 typed endpoint/field contract로 정규화하고 주변 RAG, agent, application에 필요한 가장 작은 trusted executable data surface를 검색합니다.

| 계층 | 책임 |
| --- | --- |
| 애플리케이션 / agent framework | 대화, agent loop, graph, model strategy, memory, checkpoint |
| SchemaRouter | typed tool/endpoint planning, schema identity, validation, policy, execution boundary |
| Optional decision backend | 로컬에서 허가된 유한 후보 중 bounded selection |
| Capability source | OpenAPI, MCP, OPTIMADE, Python callable, 승인된 adapter/plugin |

Laya, Ollama, Jev 같은 decision backend는 후보 선택을 보조할 뿐입니다. 새 capability를
만들거나 별도의 tool loop를 시작할 수 없고, 실행 권한도 갖지 않습니다.

## 컴파일 모델

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

Query-to-field match가 명확하면 confidently relevant field와 identifier만 유지하고, endpoint에 explicit `ServerProjectionSpec`이 있으면 해당 field를 upstream으로 push합니다. Raw projected response를 validate한 뒤 `ToolResult` 생성 전에 final local projection을 수행합니다.

지나친 pruning은 recall을 훼손할 수 있으므로 field intent가 실제로 모호하면 default planner는 한 field로 충분하다고 가장하지 않고 declared field set을 우선합니다.

[RAG positioning and capability retrieval →](capability-catalog.md) · [Field-first execution →](field-first-execution.md)

## 실행 단계에서 다시 검증하는 이유

Plan은 execution authority가 아닙니다. Planning과 execution 사이에 schema가 바뀌거나 manually constructed `ToolCall`이 malformed일 수 있고, model이 invalid value를 제안하거나 bound transport가 registered contract와 더 이상 일치하지 않을 수 있습니다.

따라서 executor는 다음 항목을 다시 확인합니다.

- 필수 argument
- schema/tool fingerprint
- local binding 준비 상태
- execution policy / approval
- input schema
- trusted transport
- raw output schema
- field projection

Executor는 required argument를 다시 계산하고 fingerprint와 policy를 검사하며 input을 validate한 뒤 trusted transport를 invoke합니다. 이후 raw output을 validate하고 마지막에 field를 projection합니다.

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

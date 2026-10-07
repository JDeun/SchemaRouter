# 왜 모든 도구 스키마를 모델에 보내지 않는가?

SchemaRouter 0.17.0은 API, 도구, 데이터 시스템 전반에서 AI 에이전트를 위한 **타입 기반 capability routing 및 governed execution layer**입니다. 에이전트가 많은 API, MCP 서버, SDK 함수, 데이터 저장소에 접근할 수 있지만 애플리케이션에는 여전히 제한되고 감사 가능한 실행 경계가 필요한 경우를 대상으로 합니다.

가장 단순한 대안은 모든 사용 가능한 도구 스키마를 모델 context에 직렬화하고 모델이 직접 고르게 하는 것입니다. 작은 catalog에서는 충분히 동작할 수 있습니다. 하지만 catalog가 커지거나, 스키마가 서로 겹치거나, 호출자마다 권한이 다르거나, 선택한 operation이 원격 상태를 변경할 수 있으면 이 방식의 비용과 위험이 커집니다.

## Retrieval은 첫 번째 경계일 뿐이다

SchemaRouter는 retrieval score를 실행 권한으로 취급하지 않습니다. 서로 다른 등록 정보를 typed capability로 컴파일하고, 제한된 candidate set을 검색한 뒤, 선택된 route를 실행 직전에 다시 검증합니다.

Capability에는 단순한 tool name보다 많은 정보가 포함될 수 있습니다.

- endpoint identity와 schema fingerprint
- typed parameter와 output field
- 알려진 경우 unit과 field semantics
- 현재 execution binding과 availability
- principal/policy constraint
- mutation 및 destructive-operation classification

따라서 shortlist는 에이전트에 유용한 context가 되지만 shortlist 자체가 신뢰된 실행 권한이 되지는 않습니다.

## 전체 catalog 대신 field-aware context

대규모 tool catalog에서는 올바른 operation을 선택하는 문제와 얼마나 많은 schema context를 노출할 것인지가 별개의 문제가 됩니다. SchemaRouter는 관련 capability의 작은 집합을 검색하고 task에 필요한 field 중심으로 output contract를 투영할 수 있습니다.

통제된 0.14 B1 mechanism 실험에서 SR-5 조건은 해당 frozen surface에서 required-route recall 100%를 유지하면서 FULL 대비 tool-schema token의 5.42%를 노출했습니다. Task pass는 SR-5 91.30%, FULL 68.48%였고 unauthorized destructive execution은 0건이었습니다. 이 수치는 통제된 benchmark의 mechanism/sanity evidence이며 모든 agent나 catalog에서 동일한 향상을 보장한다는 의미가 아닙니다.

더 강한 agent를 사용한 B2 replication과 남은 held-out/final-answer 실험은 별도로 추적합니다. SchemaRouter는 development diagnostic과 external-validation 작업을 stable product claim과 의도적으로 분리합니다.

## Unsupported request에는 policy boundary가 필요하다

등록된 capability가 요청을 지원하지 않을 때 router가 억지로 도구 하나를 선택해서는 안 됩니다. 따라서 SchemaRouter는 candidate retrieval과 execution policy를 분리하며 runtime boundary에서 fail closed할 수 있습니다.

특히 mutation에서 이 구분이 중요합니다. 모델이 destructive-looking route를 선택했다고 해서 실행 권한이 생기지 않습니다. Host가 검증된 principal context와 policy를 제공하고, runtime은 argument, schema identity, authorization, availability, output contract를 다시 검증합니다.

## Provider와 transport가 product boundary는 아니다

애플리케이션은 종종 OpenAPI, MCP, Python SDK, GraphQL, database adapter 같은 transport보다 먼저 어떤 provider를 사용할지를 결정합니다. SchemaRouter는 이러한 ingress path를 공통 capability model로 정규화합니다.

반대로 credential, connection pool, authentication, conversation memory, decomposition, final answer generation은 소유하지 않습니다. 이들은 host application이나 agent framework의 책임입니다. SchemaRouter는 이들을 대체하기보다 조합되는 것을 목표로 합니다.

## Schema와 health는 lifecycle state다

등록 시점에 존재한 route가 영원히 실행 가능하다는 보장은 없습니다. Provider는 schema를 변경하고 transport는 실패하며 local binding은 사라질 수 있습니다. SchemaRouter는 schema identity와 execution availability를 명시적으로 관리해 stale candidate가 조용히 trusted execution으로 바뀌지 않도록 합니다.

이 때문에 retrieval과 execution도 별도 API입니다. Discovery는 side-effect free로 유지하면서 executable retrieval과 runtime validation은 현재 binding과 policy를 반영할 수 있습니다.

## Framework와의 조합

SchemaRouter는 또 하나의 범용 agent loop가 아닙니다. LangChain, LangGraph, LlamaIndex, custom planner 등의 orchestrator가 reasoning과 workflow state를 계속 담당할 수 있습니다. SchemaRouter는 그 아래에서 typed catalog와 governed execution boundary 역할을 합니다.

이 좁은 범위는 의도적입니다. Prompt, memory, checkpoint, application state를 SchemaRouter로 옮기지 않고도 routing/execution contract만 도입할 수 있습니다.

## 0.17.0이 증명하지 않는 것

프로젝트는 Beta / pre-1.0이며 public API는 계속 변경될 수 있습니다.

현재 연구 evidence는 모든 full-schema agent 구성에 대한 population-level 우월성을 증명하지 않습니다. SmartMCP, Clear Your Tools, Jev, HYSET 등의 외부 시스템과 수행한 development comparison 역시 독립적인 held-out validation으로 취급하지 않습니다. 각 frozen protocol에서 재현 가능한 결과가 나온 뒤에만 해당 evidence를 구분해 보고합니다.

또한 SchemaRouter는 identity provider, database proxy, arbitrary query executor, LLM gateway가 아닙니다. Database-native grant, RLS, ACL, network control, caller-owned credential이 계속 권위 있는 경계입니다.

## 실용적인 도입 순서

하나의 실제 provider 또는 tool family부터 시작해 가장 자연스러운 ingestion path로 등록하고, catalog 범위를 넓히기 전에 컴파일된 capability를 검사하는 것이 좋습니다. 원격 mutation에 대해서는 execution policy를 deny-by-default로 유지합니다. Retrieval score 하나만 최적화하지 말고 required-tool recall, 노출된 schema context, 최종 task success, failure를 각각 측정해야 합니다.

Stable 0.17.0 release, quickstart, example, security model, 현재 research status는 모두 이 저장소에 함께 유지되며 product guarantee와 experimental evidence를 별도로 감사할 수 있습니다.

- [SchemaRouter 한국어 README](https://github.com/JDeun/SchemaRouter/blob/main/README.ko.md)
- [빠른 시작](../getting-started/quickstart.md)
- [실행 경계](../concepts/execution.md)
- [보안 모델](../security/threat-model.md)
- [연구 현황](../research/routing-status.md)
- [도입 지표](adoption-scorecard.md)

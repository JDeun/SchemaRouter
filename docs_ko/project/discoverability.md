# 검색 가능성과 포지셔닝

SchemaRouter는 일반 agent framework, MCP server 또는 model router인 것처럼 보이지 않으면서도 쉽게 발견될 수 있어야 합니다.

## 정본 포지셔닝

기본 장문 설명은 다음 문장을 사용합니다.

> **SchemaRouter는 API, 도구, 데이터 시스템 전반에서 AI agent를 위한 typed capability routing 및 governed execution layer입니다.**

보조 문구는 더 짧을 수 있지만 동일한 제품 경계를 유지해야 합니다.

### 짧은 문구

> AI agent를 위한 typed capability routing 및 governed execution.

### 생태계 문구

> 전체 capability catalog를 model context에 쏟아 넣는 대신 API, MCP tool, SDK, data system을 하나의 typed capability boundary 뒤에 둡니다.

## 무엇이고 무엇이 아닌가

SchemaRouter는 다음과 **같습니다**.

- typed tool/capability registry
- capability-retrieval layer
- schema-aware planning 및 execution boundary
- MCP/OpenAPI/Python/tool-framework integration layer
- validation, projection, policy, health, schema-lifecycle boundary

SchemaRouter는 다음과 **같지 않습니다**.

- 범용 agent framework
- LLM provider gateway
- model router
- MCP server catalog
- document retriever 또는 final-answer generator

이 구분은 기술적 정확성과 검색 품질 모두에 중요합니다. "tool routing"을 검색한 방문자가 SchemaRouter가 LLM model 사이를 routing한다고 오해하게 해서는 안 됩니다.

## 검색 용어

실제 기능을 설명할 때 다음 용어를 자연스럽게 사용합니다.

- agent tool routing
- typed tool registry
- capability retrieval
- schema-aware execution
- MCP tools
- OpenAPI tools
- JSON Schema validation
- LangChain tools
- LangGraph integration
- LlamaIndex tools
- RAG tool execution
- provider/access fallback
- field projection

검색 순위만을 위해 용어를 반복하지 않습니다.

## 노출면 정렬

모든 안정 릴리스에서 다음을 일치시켜야 합니다.

| 노출면 | 요구사항 |
| --- | --- |
| GitHub description | typed capability/execution을 설명하는 한 문장 |
| GitHub homepage | 게시된 문서 사이트 |
| GitHub topics | 실제 지원하는 protocol/framework |
| README 첫 화면 | 문제 정의 + 정본 포지셔닝 + 설치 |
| PyPI summary | 동일한 제품 범주와 경계 |
| PyPI keywords | 실제 protocol/framework/search term만 사용 |
| Docs home | 현재 안정판과 동일한 제품 경계 |
| Release notes | 안정 제품 주장과 연구 주장 분리 |

## 권장 GitHub topics

현재 topics는 의도한 표면 대부분을 이미 포함합니다. 저장소 설정을 수정할 때 정확한 기존 topic은 유지하고, 유용하다면 다음 high-signal term을 추가합니다.

- `langgraph`
- `capability-retrieval`
- `schema-aware-execution`

관련 없는 고검색량 topic은 추가하지 않습니다.

저장소 homepage는 게시된 docs URL을 유지해야 합니다. Social preview는 release checklist에서 처리합니다.

## 외부 listing 기회

Listing 제출은 대상의 자체 규칙과 SchemaRouter의 근거에 따라 결정합니다.

| 대상 | 적합성 | 현재 상태 |
| --- | --- | --- |
| `Christian-Sidak/awesome-mcp-tools` | MCP frameworks/tools | **보류**: 외부/커뮤니티 가치가 입증될 때까지 기다립니다. 해당 규칙은 피상적인 자기 홍보를 거부합니다. |
| `kaushikb11/awesome-llm-agents` | Agent Infrastructure | **아직 자격 없음**: 현재 정책상 인정된 조직/연구실이 게시하지 않았다면 최소 25 stars가 필요합니다. |
| `awesome-llms-labs/awesome-ai-agents` | Agent infrastructure/ecosystem | **보류**: 실제 외부 사용/영향이 문서화될 때까지 기다립니다. |
| Model-routing awesome lists | LLM model 간 routing | **제출하지 않음**: SchemaRouter는 tool/capability router이지 model router가 아닙니다. |
| MCP server-only catalogs | MCP servers | **제출하지 않음**: SchemaRouter는 MCP capability source를 소비/통합하지만 MCP server directory 자체는 아닙니다. |

LangChain/LlamaIndex 배포는 upstream package/listing 정책이 일반 discoverability 작업과 독립적으로 바뀔 수 있으므로 issue #10에서 별도 추적합니다.

## 릴리스 discoverability 체크리스트

안정 릴리스 전:

- [ ] README, docs home, PyPI summary, release notes가 동일한 안정 버전을 표시합니다.
- [ ] 정본 포지셔닝이 실제 제품 경계와 일치합니다.
- [ ] 새로운 protocol/framework 이름은 first-class 지원 후에만 추가합니다.
- [ ] deprecated/removed integration을 검색 metadata에서 제거합니다.
- [ ] PyPI keyword와 project URL이 유지되는 surface로 연결됩니다.
- [ ] GitHub description, topics, homepage, social preview를 검토합니다.
- [ ] 광고하는 주요 integration마다 실행 가능한 example gallery 경로가 하나 이상 있습니다.
- [ ] benchmark/research 주장은 재현 가능한 근거에 연결되고 안정 제품 주장과 분리됩니다.
- [ ] 제출 전 외부 listing 자격을 다시 확인하며 과거 contribution policy가 그대로라고 가정하지 않습니다.

## 제출 규칙

Backlink만 얻기 위해 SchemaRouter를 외부 directory에 제출하지 않습니다. 다음 조건을 모두 만족할 때만 제출합니다.

1. category가 프로젝트를 정확히 설명합니다.
2. 저장소가 해당 directory의 현재 객관적 요구사항을 충족합니다.
3. 연결된 quickstart/docs가 작동합니다.
4. 설명에 근거 없는 성능 주장이 없습니다.
5. community value를 요구하는 목록에는 충분한 외부 사용/근거가 있습니다.

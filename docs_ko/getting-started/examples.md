# 예제와 데모 모음

현재 사용하는 기술 스택에서 가장 짧게 실행할 수 있는 SchemaRouter 경로를 선택할 수 있습니다. 각 예제는 **오프라인 결정론적 예제** 또는 명시적으로 표시된 **실제·고정 공급자 검증 근거**로 구분합니다.

![SchemaRouter의 필드 우선·경로 후순위 시나리오](../assets/real-world-scenario.svg)

## 현재 사용하는 기술 스택에서 시작하기

| 가지고 있는 것 | 예제 | 확인할 수 있는 기능 |
| --- | --- | --- |
| 공급자 이름 | [Provider 중심 가이드](../guides/provider-first-registration.md) | 공급자 식별자에서 안전하게 사용할 수 있는 접근 방법 선택 |
| Python 함수 | [타입 지정 callable](https://github.com/JDeun/SchemaRouter/blob/main/examples/quickstart.py) | 타입이 있는 로컬 기능 탐색과 실행 |
| SDK/클라이언트 객체 | [SDK 바인딩 데모](https://github.com/JDeun/SchemaRouter/blob/main/examples/sdk_bound_demo.py) | 신뢰된 불투명 런타임 상태를 감싸는 명시적 계약 |
| 다수의 도구 | [컨텍스트 축소](https://github.com/JDeun/SchemaRouter/blob/main/examples/context_reduction_demo.py) | 전체 카탈로그와 제한된 Top-K 검색 비교 |
| 여러 공급자 | [혼합 공급자 데모](https://github.com/JDeun/SchemaRouter/blob/main/examples/mixed_provider_demo.py) | 상호 보완적인 의미적 필드 제공 |
| MCP stdio | [stdio 빠른 시작](https://github.com/JDeun/SchemaRouter/blob/main/examples/mcp_stdio_quickstart.py) | 실제 MCP 하위 프로세스의 기능 탐색과 실행 |
| MCP Streamable HTTP | [레퍼런스 스모크 테스트](https://github.com/JDeun/SchemaRouter/blob/main/scripts/live_reference_mcp_smoke.py) | 고정된 서버를 사용하는 실제 SDK HTTP 전송 계층 |
| OpenAPI URL | [실제 OpenAPI 빠른 시작](https://github.com/JDeun/SchemaRouter/blob/main/examples/live_openapi_quickstart.py) | 공개 공급자 탐색과 실행 |
| LangChain | [LangChain 빠른 시작](https://github.com/JDeun/SchemaRouter/blob/main/examples/langchain_quickstart.py) | `StructuredTool` 연동 |
| LangGraph | [LangGraph 빠른 시작](https://github.com/JDeun/SchemaRouter/blob/main/examples/langgraph_quickstart.py) | 그래프 노드로 사용하는 SchemaRouter |
| LlamaIndex | [LlamaIndex 빠른 시작](https://github.com/JDeun/SchemaRouter/blob/main/examples/llamaindex_quickstart.py) | `FunctionTool` 연동 |
| 영속 레지스트리·추적 기록 | [상태 검사 대시보드](https://github.com/JDeun/SchemaRouter/blob/main/examples/inspection_dashboard.py) | 실시간 검사와 정적 HTML 대시보드 |
| 변경되는 공급자 스키마 | [스키마 변경 데모](https://github.com/JDeun/SchemaRouter/blob/main/examples/schema_drift_demo.py) | 보수적인 호환성 분류 |
| 타입이 있는 실행 상태 | [상태 인식 검색](../guides/state-aware-retrieval.md) | 고정 Top-K 필터링과 유효한 Top-K 후보의 교정 보충 |
| 대규모 기능 레지스트리 | [그래프 확장성 가이드](../guides/capability-graph-scalability.md) | 인덱스·증분 그래프 구성과 벤치마크 |
| 이식 가능한 그래프 파일 | [아티팩트와 스냅샷](../guides/capability-artifacts.md) | 버전이 지정된 기능 파일의 검사·검증·마이그레이션 |
| 의사결정 관측 | [의사결정 추적 가이드](../guides/capability-decision-traces.md) | 개인정보를 보호하는 후보·제외·대체 경로 설명 |

저장소의 [예제 README](https://github.com/JDeun/SchemaRouter/tree/main/examples)에 정확한 명령, 선택적 추가 의존성, 예상 출력 구조, 근거 분류를 기재합니다.

## 실제 공급자를 사용하는 경로

사용자를 위한 빠른 시작에는 공개되어 있고, 읽기 전용이며 인증 키가 필요 없는 APIs.guru를 사용합니다.

```bash
python examples/live_openapi_quickstart.py
```

Provider-first 검증에는 Materials Project, Crossref, Tavily도 포함됩니다.

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
```

Materials Project와 Crossref 경로는 실제 읽기 전용 공급자 쿼리를 실행합니다. Tavily는 시크릿이 없을 때 인증 계약을 검증하고, `TAVILY_API_KEY`가 설정되면 실제 검색을 실행합니다.

추가적인 공개 호환성 예제는 다른 프로토콜도 다룹니다.

```bash
python scripts/live_graphql_smoke.py
python scripts/live_odata_smoke.py
```

GraphQL 예제는 Rick and Morty API를, OData 예제는 OData.org V4 레퍼런스 서비스를 사용합니다. 재료 데이터 관련 실제 검증은 COD OPTIMADE를 이용할 수 있습니다.

```bash
python scripts/live_optimade_smoke.py
```

공개 공급자의 가용성은 외부 상태이므로 이러한 경로는 예약·수동 호환성 검증 자료이지 PR 통과를 위한 필수 조건은 아닙니다.

## 고정된 프로토콜 레퍼런스

안정적인 공개 무인증 공급자가 적합하지 않으면 테스트용 데이터를 공개 실서비스 근거처럼 제시하는 대신 로컬 레퍼런스 구현을 사용합니다.

MCP stdio:

```bash
pip install "schemarouter[mcp]"
python examples/mcp_stdio_quickstart.py
```

MCP Streamable HTTP:

```bash
python scripts/live_reference_mcp_smoke.py
```

OpenRPC / JSON-RPC:

```bash
python scripts/live_reference_openrpc_smoke.py
```

## 전후 비교: 전체 스키마를 한꺼번에 전달하지 않기

실행 명령:

```bash
python examples/context_reduction_demo.py
```

이 예제는 40개 도구로 구성한 레지스트리에서 다음 직렬화 결과의 크기를 보고합니다.

- 등록된 전체 도구 카탈로그
- 제한된 Top-3 `CapabilityRetrieval` 결과

제한된 페이로드의 크기는 더 작아야 하고 날씨 관련 요청에서는 날씨 경로가 가장 먼저 선택되어야 합니다. 이는 **제품 사용 예제**이지 토큰 벤치마크가 아닙니다. 실제 모델 토큰 측정은 연구 벤치마크 모음에서 별도로 수행합니다.

## 혼합 공급자 필드 우선 계획

실행 명령:

```bash
python examples/mixed_provider_demo.py
```

한 공급자는 `band_gap`을, 다른 공급자는 `document_abstract`를 선언합니다. 요청은 두 필드를 모두 요구하며 도구 호출 2개를 허용합니다. SchemaRouter는 의미적 필드 요구사항을 먼저 컴파일하고, 이후 상호 보완적인 실행 가능한 경로를 선택합니다.

이는 하나의 논리적 답변을 만들기 위해 서로 다른 공급자의 근거를 조합할 때에도 사용하는 아키텍처입니다.

## 스키마 변경과 운영 상태 검사

오프라인 스키마 변경 분류기를 실행합니다.

```bash
python examples/schema_drift_demo.py
```

이어 [스키마 변경과 호환성](../guides/schema-drift.md)에서 원격 새로고침·감시, 보류 중인 검토, 명시적 승인·거부, 지문 동작을 확인할 수 있습니다.

런타임 관측에는 다음 명령을 사용합니다.

```bash
python examples/inspection_dashboard.py
```

이 예제는 실제 레지스트리와 추적 저장소로부터 정적 HTML 대시보드를 작성합니다. [Capability Explorer](schema-explorer.md)는 등록된 기능에 대해 프로토콜에 종속되지 않는 Swagger 방식의 화면을 제공합니다.

## CI와 재현 가능성

필수 CI는 설치된 wheel·sdist 아티팩트로 결정론적 예제를 실행합니다. 선택적 통합 작업은 해당 extra를 설치해 프레임워크 및 MCP 예제를 실행합니다. 공개 실서비스는 별도 호환성 워크플로에서 확인하므로 외부 장애가 릴리스를 막지 않습니다.

## 0.14 이후 인프라 검사

Provider-first 검증, 상태에 따른 검색, 그래프 확장성, 버전이 있는 아티팩트·스냅샷 마이그레이션, 의사결정 추적은 안정적인 실행 경계 주변에 추가된 인프라입니다.

실행할 수 있는 명령:

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
python scripts/benchmark_capability_graph.py --sizes 1000,10000,50000
```

저장되는 이식 가능한 파일에 대해서는:

```bash
schemarouter artifact inspect graph.json --json
schemarouter artifact migrate graph.json --json
schemarouter snapshot inspect snapshot.json --json
schemarouter snapshot migrate snapshot.json --json
```

의사결정 추적과 타입이 있는 상태 검색은 별도의 워크플로 런타임이 아니라 해당 가이드에서 다룹니다.
[상태 인식 검색](../guides/state-aware-retrieval.md) ·
[의사결정 추적](../guides/capability-decision-traces.md).

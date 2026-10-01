# 예제와 데모

지금 쓰고 있는 stack에 맞춰 가장 짧은 예제를 고를 수 있습니다. 외부 서비스 없이 반복 실행할 수
있는 예제와 실제 provider를 호출하는 예제를 구분해 두었습니다.

![SchemaRouter field-first, route-second scenario](../assets/real-world-scenario.svg)

## 기존 stack에서 시작하기

| 가지고 있는 것 | 예제 | 보여주는 내용 |
| --- | --- | --- |
| Python function | [typed callable](https://github.com/JDeun/SchemaRouter/blob/main/examples/quickstart.py) | typed local discovery + execution |
| SDK/client object | [SDK-bound demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/sdk_bound_demo.py) | opaque trusted runtime state 주위의 explicit contract |
| 많은 tool | [context reduction](https://github.com/JDeun/SchemaRouter/blob/main/examples/context_reduction_demo.py) | 전체 catalog와 bounded Top-K 비교 |
| 여러 provider | [mixed-provider demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/mixed_provider_demo.py) | complementary semantic-field coverage |
| MCP stdio | [stdio quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/mcp_stdio_quickstart.py) | MCP subprocess discovery + execution |
| OpenAPI URL | [live OpenAPI quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/live_openapi_quickstart.py) | 공개 provider discovery + execution |
| LangChain | [quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langchain_quickstart.py) | `StructuredTool` bridge |
| LangGraph | [quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langgraph_quickstart.py) | graph node로서의 SchemaRouter |
| LlamaIndex | [quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/llamaindex_quickstart.py) | `FunctionTool` bridge |
| Registry/trace | [inspection dashboard](https://github.com/JDeun/SchemaRouter/blob/main/examples/inspection_dashboard.py) | live inspection + static HTML dashboard |

정확한 실행 명령과 optional extras는
[repository examples README](https://github.com/JDeun/SchemaRouter/tree/main/examples)에 있습니다.

## 실제 provider 경로

인증이 필요 없는 APIs.guru:

```bash
python examples/live_openapi_quickstart.py
```

GraphQL / OData / OPTIMADE live smoke:

```bash
python scripts/live_graphql_smoke.py
python scripts/live_odata_smoke.py
python scripts/live_optimade_smoke.py
```

외부 provider의 장애 여부는 저장소가 통제할 수 없으므로 PR 통과 조건에는 넣지 않습니다.
대신 별도의 호환성 검사 결과로 기록합니다.

## 전체 schema를 모델에 던지지 않기

```bash
python examples/context_reduction_demo.py
```

40-tool registry 전체 serialization과 bounded Top-3 `CapabilityRetrieval` payload를 비교합니다.
이 예제는 토큰 성능을 주장하기 위한 benchmark가 아니라, 전체 catalog 대신 제한된 후보 계약만
전달하는 구조를 보여주기 위한 것입니다.

## 다중 provider field-first planning

```bash
python examples/mixed_provider_demo.py
```

한 provider는 `band_gap`, 다른 provider는 `document_abstract`를 제공하도록 구성합니다.
`max_calls=2`이면 SchemaRouter는 semantic field requirement를 먼저 컴파일한 후 상호 보완적인
route를 선택합니다.

## 운영 상태 확인

```bash
python examples/inspection_dashboard.py
```

실제 registry와 trace store로 static HTML dashboard를 생성합니다.

[운영 상태 확인 가이드 →](../guides/inspection.md)

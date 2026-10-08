# 빠른 시작

처음 써 볼 때는 인증키가 필요 없는 공개 OpenAPI를 사용합니다. 반대로 필수 CI는 외부 서비스가
잠시 내려가도 릴리스가 막히지 않도록 로컬 fixture로 검증합니다.

## 1. 설치

```bash
pip install schemarouter
```

이 예제에는 API key가 필요하지 않습니다.

## 2. Provider 이름으로 시작하기

사용자가 원하는 provider만 알고 protocol/SDK 구성은 모른다면 provider-first 등록을 사용합니다.

```python
from schemarouter import SchemaRouter

router = SchemaRouter()
result = await router.add_provider("materials-project")
```

SchemaRouter가 알려진 access method를 해석하고 현재 환경에서 안전하게 사용할 수 있는 method만
등록합니다. 내장 acceptance provider는 Materials Project, Crossref, Tavily, APIs.guru,
OData.org V4 reference service입니다. Credential이나 optional SDK가 없으면 추측하거나 설치하지
않고 상태로 보고합니다.

[Provider 중심 등록 자세히 보기 →](../guides/provider-first-registration.md)

## 3. 실제 provider capability 해석 및 실행

아래 예제는 내장 `apis-guru` provider profile에서 시작합니다. SchemaRouter가 provider identity를
compatibility smoke와 같은 공개 OpenAPI source로 해석한 뒤 기존 OpenAPI adapter에 전달합니다.
예제용으로 꾸며 낸 스키마나 고정 응답이 아니라 외부 provider의 실제 계약과 데이터를 사용합니다.

```python
--8<-- "examples/live_openapi_quickstart.py"
```

체크아웃한 저장소에서:

```bash
python examples/live_openapi_quickstart.py
```

성공 출력은 대략 다음 형태입니다.

```text
provider: apis-guru
source: https://api.apis.guru/v2/openapi.yaml
discovered: apis.guru:getMetrics (... endpoints on this tool)
selected: apis.guru:getMetrics
current numAPIs: <current positive integer>
```

이 예제로 다음 네 단계를 확인할 수 있습니다.

1. `add_provider("apis-guru")`가 caller가 protocol URL을 몰라도 provider profile을 해석합니다.
2. profile의 OpenAPI method가 기존 OpenAPI adapter를 거쳐 typed tool/endpoint와 stable fingerprint로 등록됩니다.
3. planner가 등록된 catalog 안에서 bounded capability를 선택합니다.
4. executor가 호출과 raw response를 검증한 뒤 `ToolResult`를 반환합니다.

## 4. 왜 live provider를 필수 CI로 쓰지 않나

공개 서비스에는 rate limit, schema 변경, 장애가 생길 수 있습니다. 그래서 필수 CI에서는
`tests/test_live_quickstart.py`의 고정 OpenAPI fixture를 process-local provider profile로 등록해
같은 provider-first 경로를 검증합니다.

로컬 callable 예제도 별도로 유지합니다.

```python
--8<-- "examples/quickstart.py"
```

이 파일은 source/wheel/sdist acceptance에서 실행됩니다.

## 5. 일반 웹사이트는 조용히 tool로 변환되지 않습니다

```python
from schemarouter import SchemaRouter, UnsupportedSchemaSourceError


async def inspect_docs_page():
    try:
        await SchemaRouter.from_url(
            "https://example.com/",
            kind="auto",
        )
    except UnsupportedSchemaSourceError:
        print("ordinary HTML was rejected as an executable source")
```

사람이 읽는 API 문서는 곧바로 실행 가능한 도구로 만들지 않습니다. 먼저 내용을 확인하고
제안된 계약을 검토한 뒤 명시적으로 승인해야 합니다.

## 6. Async / batch / streaming

```python
result = await router.ainvoke(request)

results = await router.abatch([request, request])

async for result in router.astream(request):
    print(result)

async for event in router.astream_events(request):
    print(event.event, event.tool, event.endpoint)
```

이벤트 payload는 기본 설정에서 민감한 값을 가린 상태로 기록됩니다.

## Time-to-value 예산

권장 경로는 의도적으로 다음 범위 안에 맞춰져 있습니다.

- **설치 명령 1개**: `pip install schemarouter`
- credential이 필요 없는 **실행 가능한 Python snippet 1개**
- 첫 유용한 결과 전까지 **핵심 개념 4개**: provider 이름, 해석된 capability, 선택된 plan, 검증된 결과
- database, model API, vector store, agent framework가 필요하지 않음

실제 live request 시간은 인터넷/provider latency에 좌우되지만 로컬 설정 경로에는 숨겨진 infrastructure 요구사항이 없습니다. caller가 구체적인 protocol endpoint를 이미 가지고 있다면 lower-level `from_url(...)`도 계속 사용할 수 있습니다.

## 어떤 경로를 쓰면 되나

| 이미 가지고 있는 것 | 설치 | 권장 시작점 |
| --- | --- | --- |
| Provider 이름 | `pip install schemarouter` | `await router.add_provider("materials-project")` 및 [Provider 중심 등록](../guides/provider-first-registration.md) |
| OpenAPI URL | `pip install schemarouter` | [live OpenAPI quickstart](#3-실제-provider-capability-해석-및-실행) |
| typed Python function | core install | [Python tools](../guides/python-tools.md) 및 `examples/quickstart.py` |
| MCP server | `pip install "schemarouter[mcp]"` | [MCP HTTP / stdio guide](../guides/mcp.md) |
| LangChain tools | `pip install "schemarouter[langchain]"` | `examples/langchain_quickstart.py` |
| LangGraph app | `pip install "schemarouter[langgraph]"` | `examples/langgraph_quickstart.py` |
| LlamaIndex tools | `pip install "schemarouter[llamaindex]"` | `examples/llamaindex_quickstart.py` |
| 사람이 읽는 API 문서 | core install | [inspect → proposal → approval](../guides/html-documentation.md) |

## 문제 해결

**MCP/LangChain/LlamaIndex import 오류**

해당 optional extra를 설치하십시오. core package는 모든 framework를 기본 의존성으로 가져오지
않습니다.

**401/403 또는 credentials 필요**

credential은 `trusted_headers`나 caller-owned client factory 같은 trusted runtime configuration에
두십시오. `ToolSpec`, planner argument, URL에 secret을 넣지 마십시오.

**MCP server 연결 실패**

실제로 소유한 transport를 선택하십시오. `from_url(..., kind="mcp")`를 통한 Streamable HTTP, `add_mcp_stdio()`를 통한 local stdio, 또는 `add_mcp_client_factory()`를 통한 caller-owned client lifecycle을 사용할 수 있습니다.

**Schema discovery 실패**

`router.probe_url(...)`로 privacy-safe typed diagnosis를 확인하십시오. 일반 웹사이트는 빈 tool
목록으로 조용히 실패하지 않고 명시적으로 거부됩니다.

**Discovery는 됐는데 실행이 거부됨**

Discovery는 execution authority가 아닙니다. read/write/destructive classification, execution
policy, approval callback, binding fingerprint 상태를 확인하십시오.


## 다음 단계

더 자세한 protocol 설명:

- [OpenAPI](../guides/openapi.md)
- [MCP](../guides/mcp.md)
- [GraphQL](../guides/graphql.md)
- [OData](../guides/odata.md)
- [OpenRPC / JSON-RPC](../guides/openrpc.md)
- [OPTIMADE](../guides/optimade.md)
- [Universal ingestion matrix](../guides/universal-ingestion.md)

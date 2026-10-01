# 빠른 시작

가장 짧은 사용자 경로는 실제 공개 provider를 사용합니다. 필수 CI는 외부 서비스 장애가 릴리스를
막지 않도록 offline deterministic 경로로 유지됩니다.

## 1. 설치

```bash
pip install schemarouter
```

이 예제에는 API key가 필요하지 않습니다.

## 2. 실제 OpenAPI capability 탐색 및 실행

아래 예제는 SchemaRouter의 compatibility smoke에서도 사용하는 공개 APIs.guru OpenAPI 문서를
사용합니다. 스키마와 반환값은 provider가 소유합니다.

--8<-- "examples/live_openapi_quickstart.py"

체크아웃한 저장소에서:

```bash
python examples/live_openapi_quickstart.py
```

성공 출력은 대략 다음 형태입니다.

```text
source: https://api.apis.guru/v2/openapi.yaml
discovered: apis.guru:getMetrics (... endpoints on this tool)
selected: apis.guru:getMetrics
current numAPIs: <current positive integer>
```

이 짧은 예제에서 핵심 경계 네 가지를 볼 수 있습니다.

1. `from_url(..., kind="openapi")`가 외부 machine-readable contract를 읽습니다.
2. SchemaRouter가 typed tool/endpoint와 stable fingerprint를 등록합니다.
3. planner가 등록된 catalog 안에서 bounded capability를 선택합니다.
4. executor가 호출과 raw response를 검증한 뒤 `ToolResult`를 반환합니다.

## 3. 왜 live provider를 필수 CI로 쓰지 않나

공개 서비스는 rate limit, schema change, outage가 발생할 수 있습니다. 그래서 required CI는
`tests/test_live_quickstart.py`의 deterministic OpenAPI fixture로 같은 경계를 검증합니다.

로컬 callable 예제도 별도로 유지합니다.

--8<-- "examples/quickstart.py"

이 파일은 source/wheel/sdist acceptance에서 실행됩니다.

## 4. 일반 웹사이트는 조용히 tool로 변환되지 않습니다

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

사람이 읽는 API 문서는 자동 실행 권한으로 취급하지 않고 **inspect → proposal → explicit
approval** 경로를 사용합니다.

## 5. Async / batch / streaming

```python
result = await router.ainvoke(request)

results = await router.abatch([request, request])

async for result in router.astream(request):
    print(result)

async for event in router.astream_events(request):
    print(event.event, event.tool, event.endpoint)
```

Event payload는 기본적으로 redacted 상태입니다.

## 어떤 경로를 쓰면 되나

| 이미 가지고 있는 것 | 설치 | 권장 시작점 |
| --- | --- | --- |
| OpenAPI URL | `pip install schemarouter` | 이 페이지의 live OpenAPI quickstart |
| typed Python function | core | [Python tools](../guides/python-tools.md) |
| MCP server | `schemarouter[mcp]` | [MCP](../guides/mcp.md) |
| LangChain tools | `schemarouter[langchain]` | `examples/langchain_quickstart.py` |
| LangGraph app | `schemarouter[langgraph]` | `examples/langgraph_quickstart.py` |
| LlamaIndex tools | `schemarouter[llamaindex]` | `examples/llamaindex_quickstart.py` |
| 사람이 읽는 API 문서 | core | inspect → proposal → approval |

## 문제 해결

**MCP/LangChain/LlamaIndex import 오류**

해당 optional extra를 설치하십시오. core package는 모든 framework를 기본 의존성으로 가져오지
않습니다.

**401/403 또는 credentials 필요**

credential은 `trusted_headers`나 caller-owned client factory 같은 trusted runtime configuration에
두십시오. `ToolSpec`, planner argument, URL에 secret을 넣지 마십시오.

**Schema discovery 실패**

`router.probe_url(...)`로 privacy-safe typed diagnosis를 확인하십시오. 일반 웹사이트는 빈 tool
목록으로 조용히 실패하지 않고 명시적으로 거부됩니다.

**Discovery는 됐는데 실행이 거부됨**

Discovery는 execution authority가 아닙니다. read/write/destructive classification, execution
policy, approval callback, binding fingerprint 상태를 확인하십시오.

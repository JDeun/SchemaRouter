# 선언형 HTTP/JSON tool

모든 API가 OpenAPI, MCP 또는 다른 machine-discoverable capability schema를 제공하는 것은 아닙니다. SchemaRouter는 신뢰된 로컬 `ToolSpec`을 HTTP/JSON base URL에 직접 바인딩할 수 있습니다. `ToolSpec` 자체가 manifest이며 별도의 REST 전용 schema language는 없습니다.

## REST capability 등록

```python
from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, SchemaRouter, ToolSpec

crossref = ToolSpec(
    name="crossref",
    provider="crossref",
    access_mode="rest",
    endpoints=[
        EndpointSpec(
            name="get_work",
            method="GET",
            path="/works/{doi}",
            read_only=True,
            parameters=[
                ParameterSpec(
                    name="doi",
                    required=True,
                    location="path",
                    json_schema={"type": "string"},
                ),
            ],
            output_fields=[
                FieldSpec(
                    name="message.DOI",
                    path=["message", "DOI"],
                    result_path=["message.DOI"],
                    json_schema={"type": "string"},
                    identifier=True,
                ),
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "object",
                        "properties": {
                            "DOI": {"type": "string"},
                        },
                    }
                },
            },
        )
    ],
)

router = SchemaRouter()
router.add_http_tool(
    crossref,
    base_url="https://api.crossref.org/v1",
)
```

같은 경로에서 SchemaRouter의 trusted HTTP transport가 지원하는 query/path/non-sensitive header/flattened JSON-body/root JSON-body parameter를 처리합니다.

## Secret은 manifest 밖에 유지

인증은 trusted binding에 둡니다. trusted header는 `ToolSpec`, planner state, model-selectable argument에 복사되지 않으며 선언된 header argument가 trusted header나 일반적인 민감 authorization header를 덮어쓸 수 없습니다.


```python
router.add_http_tool(
    brave_search,
    base_url="https://api.search.brave.com",
    trusted_headers={
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    },
)
```

## 언제 사용하는가

가능하면 더 풍부한 machine-readable source를 우선합니다.

1. native MCP, OPTIMADE, OpenAPI
2. 기존 typed LangChain/LlamaIndex tool import
3. typed Python callable / SDK wrapper
4. declarative HTTP/JSON ToolSpec
5. 근거가 있는 human-readable documentation proposal + 명시적 승인

이 경로는 애플리케이션이 정확한 machine-known contract를 알고 있지만 SchemaRouter가 자동 탐색할 schema endpoint는 없는 안정적인 REST API에 적합합니다.

## 같은 provider의 여러 access mode

한 provider를 `optimade`, `openapi`, `python` 등 여러 access path로 등록할 수 있습니다. route들이 호환 가능한 semantic ID, datatype, unit, qualifier를 제공한다면 `fallback_scope="same_provider"`에서 서로 다른 과학적 source로 취급하지 않고 대체 경로로 사용할 수 있습니다.


```text
provider="materials-project"
  access_mode="optimade"
  access_mode="openapi"
  access_mode="python"
```

```text
provider="tavily"
  access_mode="langchain"
  access_mode="python"
  access_mode="http_json"
```

## 안전 경계

declarative HTTP 등록은 trusted local configuration입니다. SchemaRouter는 임의 REST service를 crawl해 endpoint나 permission을 추측하지 않습니다. method/path는 명시해야 하고 mutation authority는 `ExecutionPolicy`가 관리합니다. base origin은 trusted binding으로 고정되고 credential을 base URL에 넣을 수 없으며 redirect를 추적하지 않습니다. input/output JSON Schema validation과 response size limit도 유지합니다. unit, semantic ID, qualifier, licence, normalization contract를 prose에서 추론하지 않습니다.

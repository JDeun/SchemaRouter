# Universal ingestion

SchemaRouter의 ingestion 목표는 “모든 URL을 추측해서 tool로 만든다”가 아니라 **구조화된 capability source를 가능한 한 넓게 canonical contract로 수용하되 근거가 없으면 거부하는 것**입니다.

우선순위는 native MCP/OPTIMADE/OpenAPI/GraphQL/OData/OpenRPC → typed Python/SDK/framework tool → declarative HTTP/JSON → grounded human-readable documentation proposal입니다. 일반 웹 페이지는 실행 가능한 API schema로 조용히 받아들이지 않습니다.

`kind="auto"`는 deterministic adapter priority와 passive discovery profile을 사용합니다. active probe는 opt-in이고 unsupported source는 명확한 diagnostic을 반환합니다. provider별 protocol 차이는 adapter에서 끝나며 planner/executor는 동일한 typed contract를 사용합니다.


## Provider 이름을 알고 있는 경우

사용자가 원하는 서비스는 알지만 OpenAPI/OPTIMADE/SDK 구성을 모른다면 protocol을 먼저 고르게
하지 않습니다.

```python
result = await router.add_provider("materials-project")
```

`ProviderProfile`이 provider identity를 선언된 access method로 해석한 뒤 기존
OpenAPI/OPTIMADE/HTTP-JSON/Python/plugin ingestion으로 위임합니다. Provider-specific planner를
추가하는 것이 아니며 같은 provider라고 해서 method 간 semantic compatibility가 자동으로
생기지도 않습니다.

현재 built-in acceptance profile은 Materials Project, Crossref, Tavily입니다. Materials
Project는 공개 OPTIMADE + 인증 OpenAPI + optional mp-api, Crossref는 공개 HTTP/JSON,
Tavily는 인증 HTTP/JSON + optional Python SDK 경로를 갖습니다.


## 지원 ingestion mode

| Mode | 사용 시점 | Public entry point |
| --- | --- | --- |
| Provider profile | provider는 알지만 protocol/SDK 전체를 모를 때 | `await router.add_provider(...)` |
| Direct ToolSpec | application이 canonical contract를 이미 소유할 때 | `router.add_tool(...)` |
| Python | SDK/function이 안정적인 typed signature를 가질 때 | `router.add_callable(...)` |
| ToolSpec + SDK/client | SDK/client를 안전하게 introspect하기 어려울 때 | `router.add_bound_tool(...)` |
| OpenAPI | HTTP API가 OpenAPI/Swagger를 제공할 때 | `from_url(..., kind="openapi")` |
| MCP Streamable HTTP | remote MCP server를 HTTP로 연결할 때 | `from_url(..., kind="mcp")` |
| MCP stdio | local MCP server를 trusted subprocess로 실행할 때 | `router.add_mcp_stdio(...)` |
| MCP custom transport | application이 MCP client lifecycle을 직접 소유할 때 | `router.add_mcp_client_factory(...)` |
| OPTIMADE | materials data가 OPTIMADE로 제공될 때 | `from_url(..., kind="optimade")` |
| GraphQL | introspection + native selection set을 사용할 수 있을 때 | `from_url(..., kind="graphql")` |
| OData | CSDL/`$metadata`와 `$select`가 있을 때 | `from_url(..., kind="odata")` |
| OpenRPC | JSON-RPC service가 OpenRPC를 제공할 때 | `from_url(..., kind="openrpc")` |
| LangChain tool | 기존 LangChain tool을 가져올 때 | `router.add_langchain_tool(...)` |
| LlamaIndex tool | 기존 LlamaIndex tool을 가져올 때 | `router.add_llamaindex_tool(...)` |
| REST/JSON | discoverable schema는 없지만 trusted REST contract가 있을 때 | `router.add_http_tool(...)` |
| Custom protocol | custom discovery/transport가 필요할 때 | `router.register_adapter(...)` |
| Human-readable docs | machine-readable contract가 없을 때 | inspect → proposal → explicit approval |

Core에 protocol-specific adapter를 추가하는 기준은 generic HTTP/Python/plugin 경로로는 보존하기
어려운 machine-readable schema 의미가 실제로 있는가입니다.

## 네트워크 신뢰 경계

URL 기반 discovery와 execution은 네트워크 신뢰 경계입니다. 기본
`NetworkPolicy.trusted_internal()`은 기존 local/intranet 배포를 보존하므로, model 또는
사용자 입력이 결정하는 URL을 기본 설정에 그대로 전달해서는 안 됩니다.

신뢰도가 낮은 입력이 URL에 영향을 줄 수 있다면 public-network 정책을 명시합니다.

```python
from schemarouter import NetworkPolicy, SchemaRouter

router = SchemaRouter(
    network_policy=NetworkPolicy.public_only(
        allowed_ports={80, 443},
    )
)
await router.add_url("https://api.example.com/openapi.json", kind="openapi")
```

Public profile은 loopback, link-local, private, multicast/reserved 및 일반적인 cloud metadata
목적지를 거부합니다. Hostname은 IDNA 정규화 후 네트워크 접근 직전에 resolve하며, redirect와
외부 OpenAPI reference도 매번 다시 검사합니다. 같은 정책이 OpenAPI/HTTP JSON, GraphQL,
OData, OpenRPC, OPTIMADE, MCP HTTP 실행 binding에도 전달됩니다.

의도적으로 사용하는 내부 서비스는 `allowed_hosts`로 명시적으로 신뢰할 수 있습니다.
Trusted header는 cross-origin schema redirect로 전달되지 않으며, redirect를 지원하지 않는
protocol adapter는 기존과 같이 redirect를 거부합니다.

DNS 정책 검사와 HTTP client의 실제 connection lookup은 별도 단계입니다. 따라서 built-in
public policy는 DNS rebinding 노출을 줄이지만 connection-level DNS pinning까지 보장하지는
않습니다. 더 강한 보장이 필요하면 검증한 주소를 pin하는 transport/resolver 조합을 사용하거나
동일한 egress 정책을 네트워크 계층에서도 강제해야 합니다.

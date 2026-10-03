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

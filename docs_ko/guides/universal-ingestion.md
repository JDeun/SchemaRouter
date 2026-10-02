# Universal ingestion

SchemaRouter의 ingestion 목표는 “모든 URL을 추측해서 tool로 만든다”가 아니라 **구조화된 capability source를 가능한 한 넓게 canonical contract로 수용하되 근거가 없으면 거부하는 것**입니다.

우선순위는 native MCP/OPTIMADE/OpenAPI/GraphQL/OData/OpenRPC → typed Python/SDK/framework tool → declarative HTTP/JSON → grounded human-readable documentation proposal입니다. 일반 웹 페이지는 실행 가능한 API schema로 조용히 받아들이지 않습니다.

`kind="auto"`는 deterministic adapter priority와 passive discovery profile을 사용합니다. active probe는 opt-in이고 unsupported source는 명확한 diagnostic을 반환합니다. provider별 protocol 차이는 adapter에서 끝나며 planner/executor는 동일한 typed contract를 사용합니다.

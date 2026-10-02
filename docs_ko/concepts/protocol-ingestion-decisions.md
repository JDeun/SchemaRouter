# Protocol ingestion 결정

호환성 목록을 늘리기 위해 모든 protocol을 built-in으로 추가하지 않습니다. machine-readable capability semantics, native projection, execution lifecycle 정보가 OpenAPI/Python/inbound tools/declarative HTTP/plugin 경로에서 손실될 때만 first-class adapter가 정당화됩니다.

GraphQL은 introspection과 selection set, OData는 CSDL과 `$select`, OpenRPC는 typed JSON-RPC method/result 때문에 first-class 가치가 있습니다. STAC은 OpenAPI를 우선하고 필요한 경우 overlay/plugin을 사용합니다. gRPC/Protobuf와 SOAP/WSDL은 transport/lifecycle 복잡성 때문에 official plugin 우선, AsyncAPI는 durable event lifecycle contract가 생기기 전 core에서 보류합니다.

built-in 승격 조건은 안정적인 machine-readable discovery, generic 경로에서 잃는 semantics, 안전하게 표현 가능한 lifecycle, explicit local authority, deterministic drift detection, public network 없이 가능한 representative conformance test입니다.

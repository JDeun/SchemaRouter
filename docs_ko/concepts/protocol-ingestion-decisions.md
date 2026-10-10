# Protocol ingestion decisions

SchemaRouter는 compatibility list를 늘리기 위해 모든 protocol의 built-in adapter를 추가하지 않습니다. Protocol-specific adapter는 OpenAPI, Python callable, inbound agent tool, declarative HTTP/JSON, SourceAdapter plugin을 통하면 잃게 되는 machine-readable capability semantics, server-side projection 또는 execution lifecycle information을 보존할 때만 정당화됩니다.

## Decision matrix

| Protocol | Discovery surface | Projection/lifecycle value | Recommendation |
| --- | --- | --- | --- |
| GraphQL | schema introspection | selection sets, typed query/mutation arguments | **first-class adapter candidate** |
| OData | CSDL / `$metadata` | typed entity fields, functions/actions, `$select` | **first-class adapter candidate** |
| OpenRPC / JSON-RPC | OpenRPC document / `rpc.discover` | typed params/results, JSON-RPC method envelope | **first-class adapter candidate** |
| STAC API | 보통 OpenAPI + STAC conformance metadata | Fields extension, geospatial catalog semantics | OpenAPI 우선; 필요 시 official overlay/plugin |
| gRPC / Protobuf | descriptors / proto files | strongly typed RPC, binary transport, streaming | official plugin 우선 |
| SOAP / WSDL | WSDL/XSD | typed enterprise operations, XML envelopes | official plugin 우선 |
| AsyncAPI | AsyncAPI document | publish/subscribe/event lifecycle | core defer; bounded request/reply용 plugin |
| JSON-RPC without OpenRPC | standard machine-readable method catalog 없음 | envelope only | declarative HTTP/plugin; automatic discovery 없음 |

## GraphQL

GraphQL introspection은 root query/mutation/subscription type, named type, field, argument, description, deprecation metadata를 노출합니다.

- 루트 질의 필드 → 읽기 중심 엔드포인트
- root mutation field -> mutation endpoint, 자동 authorization은 아님
- argument -> `ParameterSpec`
- return field -> `FieldSpec`
- 선택 필드 집합 → 호출을 인식하는 서버 측 필드 투영
- 중첩 GraphQL 필드 → 계획기가 확인할 수 있는 명시적 경로

Field selection 자체가 protocol의 first-class 부분이므로 generic HTTP보다 실제 가치가 있습니다. Subscription은 long-lived stream lifecycle contract가 생길 때까지 initial implementation 밖에 둡니다.

## OData

OData는 `$metadata`로 machine-readable CSDL을 노출합니다. Entity set, complex type, function, action이 typed SchemaRouter capability에 대응합니다.

`$select`는 explicit server-side field projection이고 `$filter`, `$orderby`, paging syntax는 protocol-owned query semantics입니다.

Initial scope:

- entity reads
- functions
- `$select` projection
- pagination

OData action/write는 explicit local side-effect classification을 유지해야 합니다.

## OpenRPC / JSON-RPC

OpenRPC는 JSON-RPC 2.0의 machine-readable interface description입니다. Method, parameter, result schema, component, service discovery가 SchemaRouter contract에 자연스럽게 대응합니다.

- OpenRPC method -> `EndpointSpec`
- params -> `ParameterSpec`
- result JSON Schema -> output contract
- JSON-RPC 메서드 이름 → 신뢰된 전송 계층 메타데이터
- `rpc.discover` -> optional schema discovery/refresh

OpenRPC 없는 plain JSON-RPC endpoint에는 standard discovery information이 충분하지 않습니다. Method surface를 추측하지 말고 trusted declarative contract/plugin을 사용합니다.

## STAC

STAC API는 보통 OpenAPI를 이미 노출하므로 duplicate full STAC parser 대신 OpenAPI path를 우선합니다.

STAC-specific metadata가 planning을 실질적으로 개선할 때 official overlay/plugin이 유용합니다.

- collection/item semantics
- conformance classes
- include/exclude projection용 Fields extension
- geospatial/temporal query semantics

Overlay는 canonical OpenAPI contract를 fork하지 않고 augment해야 합니다.

## gRPC / Protocol Buffers

Protocol Buffer descriptor는 strong typed service/method/input/output contract를 제공하지만 gRPC는 binary transport와 unary/server-stream/client-stream/bidirectional-stream lifecycle을 도입합니다.

- official plugin 우선
- unary RPC는 normal `ToolCall`로 mapping 가능
- streaming RPC는 built-in support 전 separate lifecycle contract 필요
- generated Python stub은 typed Python callable로 이미 wrap 가능

## SOAP / WSDL

WSDL/XSD는 machine-readable operation/message schema를 제공하지만 SOAP은 XML namespace/envelope/fault/enterprise authentication pattern을 추가합니다.

Core보다 official plugin을 권장합니다. Canonical `ToolSpec`은 충분하고 XML transport detail은 protocol-neutral core 밖에 둡니다.

## AsyncAPI

AsyncAPI는 event-driven channel/message/publisher/subscriber를 기술합니다. Long-lived subscription/callback은 현재 single-call execution abstraction에 잘 맞지 않습니다.

- event subscription을 synchronous tool로 가장하지 않음
- bounded request/reply interaction용 official plugin 허용
- durable subscription/event lifecycle 이후에만 built-in 재검토

## Adapter promotion rule

Plugin/example에서 built-in으로 승격하려면 모두 만족해야 합니다.

1. stable machine-readable discovery contract
2. generic HTTP/Python이 잃는 field/parameter semantics
3. transport lifecycle을 SchemaRouter가 안전하게 표현 가능
4. security authority가 explicit/local 유지
5. schema drift deterministic detection 가능
6. public network availability에 의존하지 않는 representative conformance test

Core는 작게 유지하면서 ingestion surface는 넓게 만드는 기준입니다.

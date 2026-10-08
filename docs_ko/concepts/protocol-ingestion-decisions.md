# Protocol ingestion 결정

SchemaRouter는 compatibility 목록을 늘리기 위한 목적으로 모든 protocol에 built-in adapter를 추가해서는 안 됩니다. A protocol-specific adapter is justified only when it preserves machine-readable capability
semantics, server-side projection, or execution lifecycle information that would otherwise be lost
through OpenAPI, Python callables, inbound agent tools, declarative HTTP/JSON, or a SourceAdapter
plugin.

## 결정 matrix

| Protocol | Discovery surface | Projection/lifecycle value | Recommendation |
| --- | --- | --- | --- |
| GraphQL | schema introspection | selection sets, typed query/mutation arguments | **first-class adapter candidate** |
| OData | CSDL / `$metadata` | typed entity fields, functions/actions, `$select` | **first-class adapter candidate** |
| OpenRPC / JSON-RPC | OpenRPC document / `rpc.discover` | typed params/results, JSON-RPC method envelope | **first-class adapter candidate** |
| STAC API | usually OpenAPI + STAC conformance metadata | Fields extension and geospatial catalog semantics | OpenAPI first; official overlay/plugin if needed |
| gRPC / Protobuf | descriptors / proto files | strongly typed RPC, binary transport, streaming | official plugin first |
| SOAP / WSDL | WSDL/XSD | typed enterprise operations and XML envelopes | official plugin first |
| AsyncAPI | AsyncAPI document | publish/subscribe/event lifecycle | defer core; plugin for bounded request/reply only |
| JSON-RPC without OpenRPC | no standard machine-readable method catalog | envelope only | declarative HTTP/plugin; no automatic discovery |

## GraphQL

GraphQL introspection exposes root query, mutation, subscription types, named types, fields,
arguments, descriptions, and deprecation metadata. This maps naturally to SchemaRouter:

- root query fields -> read-oriented endpoints;
- root mutation fields -> mutation endpoints, but never automatically authorized;
- arguments -> `ParameterSpec`;
- return fields -> `FieldSpec`;
- selection sets -> call-aware server projection;
- nested GraphQL fields -> explicit planner-visible paths.

A GraphQL adapter adds real value over generic HTTP because field selection is a first-class part of
the protocol. Subscriptions should remain out of the initial implementation until SchemaRouter has a
long-lived stream lifecycle contract.

## OData

OData services expose machine-readable CSDL through `$metadata`. Entity sets, complex types,
functions, and actions map to typed SchemaRouter capabilities.

`$select` gives an explicit server-side field projection mechanism, and `$filter`, `$orderby`,
and paging syntax are protocol-owned query semantics.

Initial scope should prioritize:
- entity reads;
- functions;
- `$select` projection;
- pagination.

OData actions and write operations must keep explicit local side-effect classification.

## OpenRPC / JSON-RPC

OpenRPC is a machine-readable interface description for JSON-RPC 2.0. Methods, parameters, result
schemas, components, and service discovery map cleanly to SchemaRouter contracts.

Recommended mapping:
- OpenRPC method -> `EndpointSpec`;
- params -> `ParameterSpec`;
- result JSON Schema -> output contract;
- JSON-RPC method name -> trusted transport metadata;
- `rpc.discover` -> optional schema discovery/refresh path.

A plain JSON-RPC endpoint without OpenRPC does not contain enough standard discovery information.
Use a trusted declarative contract or plugin instead of guessing method surfaces.

## STAC

STAC APIs commonly already expose OpenAPI, so SchemaRouter should prefer the OpenAPI path rather
than maintain a duplicate full STAC parser.

An official STAC overlay/plugin becomes useful where STAC-specific metadata materially improves
planning:
- collection/item semantics;
- conformance classes;
- the Fields extension for include/exclude projection;
- geospatial/temporal query semantics.

The overlay should augment, not fork, the canonical OpenAPI contract.

## gRPC / Protocol Buffers

Protocol Buffer descriptors provide strong typed service/method/input/output contracts. However,
gRPC introduces binary transport and unary/server-stream/client-stream/bidirectional-stream
lifecycles.

Recommendation:
- official plugin first;
- unary RPCs can map to normal `ToolCall`;
- streaming RPCs require a separate lifecycle contract before built-in support;
- generated Python stubs may already be wrapped through typed Python callables.

## SOAP / WSDL

WSDL and XSD provide machine-readable operation and message schemas, but SOAP adds XML namespaces,
envelopes, faults, and enterprise authentication patterns.

Recommendation: official plugin rather than core. The canonical `ToolSpec` remains sufficient,
while XML transport details stay outside the protocol-neutral core.

## AsyncAPI

AsyncAPI describes event-driven channels, messages, publishers, and subscribers. Long-lived
subscriptions and callbacks do not fit the current single-call execution abstraction cleanly.

Recommendation:
- do not pretend an event subscription is a synchronous tool;
- permit official plugins for bounded request/reply interactions;
- revisit built-in support only after a durable subscription/event lifecycle exists.

## Adapter promotion rule

A protocol moves from plugin/example to built-in only when all of these are true:

1. there is a stable machine-readable discovery contract;
2. the protocol carries field/parameter semantics that generic HTTP/Python would lose;
3. its transport lifecycle fits or can be represented safely by SchemaRouter;
4. security authority can remain explicit and local;
5. schema drift can be detected deterministically;
6. representative conformance tests can run without depending on public network availability.

This keeps SchemaRouter's core small while making its ingestion surface broad.

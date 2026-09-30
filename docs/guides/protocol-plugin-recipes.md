# Protocol plugin recipes

SchemaRouter's compatibility surface is deliberately wider than its built-in adapter list.

A provider or protocol does **not** need a core adapter merely because its wire format is different.
Use the narrowest ingestion path that preserves the source contract without losing authority,
projection, or lifecycle semantics.

## Decision table

| Protocol/source | Preferred path | When a plugin is justified |
| --- | --- | --- |
| STAC API | published OpenAPI | STAC-specific collection/conformance/Fields semantics are absent from the OpenAPI contract |
| gRPC / Protobuf unary RPC | typed Python wrapper around generated stub | descriptor discovery across many services/methods must be automatic |
| SOAP / WSDL | SourceAdapter plugin | operations/types must be discovered from WSDL/XSD |
| AsyncAPI request/reply | SourceAdapter plugin | machine-readable message/channel contracts add value |
| AsyncAPI subscriptions/webhooks | **not a normal ToolCall** | wait for an explicit long-lived event lifecycle |
| JSON-RPC with OpenRPC | built-in OpenRPC adapter | no plugin needed |
| GraphQL | built-in GraphQL adapter | no plugin needed when introspection is available |
| OData | built-in OData adapter | no plugin needed for supported entity-set reads |

## STAC: OpenAPI first

Many STAC APIs publish an OpenAPI document. Register that document normally:

```python
router = await SchemaRouter.from_url(
    "https://stac.example/openapi.json",
    kind="openapi",
)
```

If the published contract already declares the Item Search parameters and response fields, a
STAC-specific adapter would duplicate the OpenAPI parser.

A plugin becomes useful only when STAC-specific metadata changes routing or projection, for example:

- collection/item identity;
- conformance classes;
- the Fields extension's include/exclude semantics;
- geospatial or temporal query semantics not represented in the OpenAPI document.

In that case the plugin should compile those semantics into ordinary `ParameterSpec`,
`FieldSpec`, and `ServerProjectionSpec` values. The planner itself remains STAC-neutral.

## gRPC unary RPC: typed Python is already a valid ingestion path

Generated gRPC stubs are local Python objects. For a bounded unary RPC, wrap the generated method in
a typed callable rather than introducing protobuf transport logic into the core:

```python
from pydantic import BaseModel
from schemarouter import SchemaRouter, schema_tool


class MaterialReply(BaseModel):
    material_id: str
    band_gap: float


@schema_tool(
    read_only=True,
    provider="materials-grpc",
    access_mode="grpc",
)
def get_material(material_id: str) -> MaterialReply:
    request = generated_pb2.GetMaterialRequest(material_id=material_id)
    reply = stub.GetMaterial(request)
    return MaterialReply(
        material_id=reply.material_id,
        band_gap=reply.band_gap,
    )


router = SchemaRouter()
router.add_callable(get_material)
```

This keeps protobuf messages and channel credentials inside trusted application code while exposing a
normal typed capability to SchemaRouter.

### When a gRPC plugin adds value

Use a plugin when the application needs automatic descriptor-driven discovery across many methods.
The plugin may read trusted protobuf descriptors and compile:

- service + method -> `EndpointSpec`;
- request descriptor -> input JSON Schema / `ParameterSpec`;
- response descriptor -> output JSON Schema / `FieldSpec`;
- unary transport -> a private invoker.

Do **not** silently map server-streaming, client-streaming, or bidirectional-streaming RPCs to a
single ordinary `ToolCall`. They need a lifecycle contract that preserves cancellation,
backpressure, partial delivery, and stream completion.

## SOAP / WSDL: plugin, not core

WSDL/XSD is machine-readable enough to discover operations and message types, but SOAP adds
namespaces, XML envelopes, faults, WS-* authentication, and transport details that do not belong in
the protocol-neutral planner.

An official plugin should follow this shape:

```python
class WsdlAdapter:
    kind = "wsdl"
    priority = 40

    async def load(self, context):
        wsdl = await trusted_wsdl_loader(
            context.url,
            headers=context.schema_headers,
        )

        tool = compile_wsdl_to_tool_spec(wsdl)

        invoker = SoapInvoker(
            approved_service_url=trusted_service_url,
            credentials=trusted_runtime_credentials,
        )
        return AdapterLoadResult(tool=tool, invoker=invoker)
```

The compiler owns XML/WSDL interpretation. The returned `ToolSpec` must still preserve the common
SchemaRouter boundaries:

- typed input/output contracts;
- explicit local side-effect classification;
- fingerprinted execution metadata;
- credentials outside model-visible schemas;
- bounded response handling;
- deterministic fault handling.

Remote WSDL prose or operation names must not grant write authority.

## AsyncAPI: distinguish request/reply from subscriptions

AsyncAPI can describe publish/subscribe channels and message schemas. The message schema can map to
SchemaRouter contracts, but the lifecycle matters more than the shape.

A bounded request/reply interaction can be exposed by a plugin when the adapter can guarantee one
request maps to one bounded result.

A long-lived subscription, webhook callback, or continuously delivered topic is **not** equivalent
to a normal tool invocation. Do not fake one by blocking indefinitely or returning an arbitrary
first event.

Until SchemaRouter has an explicit event/subscription lifecycle, keep these operations outside the
ordinary `ToolCall` abstraction.

## Plugin package boundary

Third-party protocol packages should publish through the existing entry-point group:

```toml
[project.entry-points."schemarouter.adapters"]
wsdl = "schemarouter_wsdl:WsdlAdapter"
grpc_descriptor = "schemarouter_grpc:GrpcDescriptorAdapter"
```

Loading remains explicit:

```python
router.load_adapter_plugins(
    allowlist={"wsdl", "grpc_descriptor"},
)
```

Discovery alone never imports plugin code. Remote content cannot request plugin loading.

## Promotion rule

A plugin should become a built-in adapter only if repeated use demonstrates that:

1. there is a stable machine-readable discovery contract;
2. generic OpenAPI/Python/HTTP/agent-tool ingestion loses material semantics;
3. execution lifecycle fits SchemaRouter safely;
4. authority and credentials remain explicit local state;
5. schema drift can be fingerprinted deterministically;
6. representative tests can run offline.

This keeps the core small while allowing the ecosystem to cover substantially more protocols and
domains than the built-in list alone.

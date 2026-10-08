# Protocol plugin recipes

SchemaRouter의 compatibility surface는 의도적으로 built-in adapter 목록보다 넓습니다.

provider나 protocol은 wire format이 다르다는 이유만으로 core adapter가 필요한 것이 **아닙니다**. authority, projection, lifecycle semantic을 잃지 않으면서 source contract를 보존하는 가장 좁은 ingestion path를 사용합니다.

## 선택 기준

| Protocol/source | 권장 path | plugin이 필요한 경우 |
| --- | --- | --- |
| STAC API | published OpenAPI | OpenAPI contract에 STAC-specific collection/conformance/Fields semantic이 없는 경우 |
| gRPC / Protobuf unary RPC | generated stub을 감싼 typed Python wrapper | 여러 service/method의 descriptor discovery를 자동화해야 하는 경우 |
| SOAP / WSDL | SourceAdapter plugin | WSDL/XSD에서 operation/type을 discover해야 하는 경우 |
| AsyncAPI request/reply | SourceAdapter plugin | machine-readable message/channel contract가 유용한 경우 |
| AsyncAPI subscriptions/webhooks | **일반 ToolCall이 아님** | 명시적인 long-lived event lifecycle이 필요 |
| JSON-RPC with OpenRPC | built-in OpenRPC adapter | plugin 불필요 |
| GraphQL | built-in GraphQL adapter | introspection 사용 가능 시 plugin 불필요 |
| OData | built-in OData adapter | 지원되는 entity-set read에는 plugin 불필요 |

## STAC: OpenAPI 우선

많은 STAC API가 OpenAPI document를 제공합니다. 해당 document를 일반적인 방식으로 등록합니다:

```python
router = await SchemaRouter.from_url(
    "https://stac.example/openapi.json",
    kind="openapi",
)
```

공개된 contract가 이미 Item Search parameter와 response field를 선언한다면 STAC-specific adapter는 OpenAPI parser를 중복 구현하게 됩니다.

STAC-specific metadata가 routing 또는 projection을 바꾸는 경우에만 plugin이 유용합니다. 예:

- collection/item identity
- conformance class
- Fields extension의 include/exclude semantic
- OpenAPI document에 표현되지 않은 geospatial/temporal query semantic

이 경우 plugin은 해당 semantic을 일반 `ParameterSpec`, `FieldSpec`, `ServerProjectionSpec` 값으로 compile해야 합니다. planner 자체는 STAC-neutral하게 유지됩니다.

## gRPC unary RPC: typed Python도 유효한 ingestion path

생성된 gRPC stub은 local Python object입니다. bounded unary RPC에서는 protobuf transport logic을 core에 넣는 대신 생성 method를 typed callable로 감쌉니다:

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

이를 통해 protobuf message와 channel credential은 trusted application code 내부에 유지하면서 SchemaRouter에는 일반 typed capability를 노출합니다.

### gRPC plugin이 필요한 경우

여러 method에 대한 automatic descriptor-driven discovery가 필요할 때 plugin을 사용합니다.
plugin은 trusted protobuf descriptor를 읽어 다음을 compile할 수 있습니다:

- service + method -> `EndpointSpec`;
- request descriptor -> input JSON Schema / `ParameterSpec`;
- response descriptor -> output JSON Schema / `FieldSpec`;
- unary transport -> a private invoker.

server-streaming, client-streaming, bidirectional-streaming RPC를 일반 `ToolCall` 하나에 묵시적으로 매핑해서는 **안 됩니다**. cancellation, backpressure, partial delivery, stream completion을 보존하는 lifecycle contract가 필요합니다.

## SOAP / WSDL: core가 아닌 plugin

WSDL/XSD는 operation과 message type을 discover할 만큼 machine-readable하지만 SOAP에는 protocol-neutral planner에 속하지 않는 namespace, XML envelope, fault, WS-* authentication, transport detail이 추가됩니다.

official plugin은 다음 형태를 따라야 합니다:

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

compiler가 XML/WSDL interpretation을 담당합니다. 반환된 `ToolSpec`은 공통 SchemaRouter boundary를 계속 보존해야 합니다:

- typed input/output contracts;
- explicit local side-effect classification;
- fingerprinted execution metadata;
- credentials outside model-visible schemas;
- bounded response handling;
- deterministic fault handling.

remote WSDL prose나 operation name이 write authority를 부여해서는 안 됩니다.

## AsyncAPI: request/reply와 subscription 구분

AsyncAPI는 publish/subscribe channel과 message schema를 기술할 수 있습니다. message schema를 SchemaRouter contract에 매핑할 수 있지만 shape보다 lifecycle이 더 중요합니다.

adapter가 하나의 request를 하나의 bounded result에 매핑한다고 보장할 수 있다면 bounded request/reply interaction을 plugin으로 노출할 수 있습니다.

long-lived subscription, webhook callback, continuously delivered topic은 일반 tool invocation과 동등하지 **않습니다**. 무기한 block하거나 임의의 첫 event를 반환하는 방식으로 이를 흉내 내지 않습니다.

SchemaRouter가 명시적인 event/subscription lifecycle을 갖추기 전까지 이러한 operation은 일반 `ToolCall` abstraction 외부에 유지합니다.

## Plugin package 경계

third-party protocol package는 기존 entry-point group을 통해 publish해야 합니다:

```toml
[project.entry-points."schemarouter.adapters"]
wsdl = "schemarouter_wsdl:WsdlAdapter"
grpc_descriptor = "schemarouter_grpc:GrpcDescriptorAdapter"
```

loading은 명시적으로 수행합니다:

```python
router.load_adapter_plugins(
    allowlist={"wsdl", "grpc_descriptor"},
)
```

discovery만으로 plugin code를 import하지 않으며 remote content가 plugin loading을 요청할 수도 없습니다.

## Built-in 승격 기준

반복 사용을 통해 다음 조건이 입증될 때만 plugin을 built-in adapter로 승격해야 합니다:

1. stable machine-readable discovery contract가 있음
2. generic OpenAPI/Python/HTTP/agent-tool ingestion에서 중요한 semantic이 손실됨
3. execution lifecycle이 SchemaRouter에 안전하게 부합함
4. authority와 credential이 explicit local state로 유지됨
5. schema drift를 deterministic하게 fingerprint할 수 있음
6. representative test를 offline에서 실행할 수 있음

이를 통해 core는 작게 유지하면서 ecosystem은 built-in 목록보다 훨씬 많은 protocol과 domain을 지원할 수 있습니다.

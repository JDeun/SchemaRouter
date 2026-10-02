# Protocol plugin recipe

built-in이 아닌 protocol은 `SourceAdapter` plugin으로 canonical contract에 연결할 수 있습니다. STAC overlay, gRPC/Protobuf unary RPC, SOAP/WSDL, bounded AsyncAPI request/reply 같은 경우가 대표적입니다.

plugin은 discovery와 transport lifecycle을 protocol 내부에 가두고 `ToolSpec/EndpointSpec/ParameterSpec/FieldSpec`을 반환해야 합니다. streaming/subscription처럼 현재 single-call abstraction과 맞지 않는 lifecycle을 synchronous tool처럼 위장하지 않습니다.

server-side projection, schema fingerprint, origin/credential separation, side-effect classification, refresh profile을 명시적으로 구현하고 deterministic fixture conformance test를 제공해야 합니다. plugin은 allowlist로만 로드됩니다.

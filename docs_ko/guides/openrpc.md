# OpenRPC / JSON-RPC

SchemaRouter는 OpenRPC 문서를 수집해 JSON-RPC method를 다른 source와 동일한 `ToolSpec -> EndpointSpec -> ParameterSpec -> FieldSpec` 모델로 컴파일합니다.

## OpenRPC 서비스 등록

```python
router = await SchemaRouter.from_url(
    "https://rpc.example/openrpc.json",
    kind="openrpc",
)
```

OpenRPC method name은 endpoint name이 되고, 선언된 param은 typed argument, result JSON Schema는 output contract가 됩니다. `components` 아래 local `$ref`를 해석하며 nested object와 array-item field도 planner에 노출합니다. projection 과정에서도 record alignment를 유지합니다.

## 실행 권한은 로컬에 유지

OpenRPC는 interface shape를 설명할 뿐 신뢰할 수 있는 side-effect policy가 아닙니다. 따라서 SchemaRouter는 description/tag를 근거로 method를 read-only 또는 mutating으로 지정하지 않습니다.

원격 OpenRPC method는 기본적으로 unclassified이며 기본 execution policy에서 fail-closed됩니다. 권한은 trusted local policy 또는 trusted contract amendment로 부여해야 합니다.

## Server binding

문서가 schema URL과 같은 origin의 HTTP(S) server를 광고하면 자동 바인딩할 수 있습니다. cross-origin server는 제안으로만 취급합니다.

```python
router = await SchemaRouter.from_url(
    "https://schema.example/openrpc.json",
    kind="openrpc",
    base_url="https://approved-rpc.example/rpc",
)
```

명시적 `base_url`이 trusted local approval boundary입니다. 인증 header도 trusted runtime binding에 속하며 model-visible contract에 들어가지 않습니다.


```python
router = await SchemaRouter.from_url(
    "https://rpc.example/openrpc.json",
    kind="openrpc",
    trusted_headers={"Authorization": f"Bearer {token}"},
)
```

## Parameter 구조

OpenRPC `by-name`, `either` method는 JSON object param으로 전송합니다. `by-position`은 보수적으로 지원하며, 앞선 optional positional parameter를 생략하고 뒤 parameter만 제공해 의미가 이동하는 호출은 거부합니다.

## Response validation

transport는 HTTP status, response-size bound, JSON decoding, `jsonrpc == "2.0"`, request/response ID 일치, application-level `error` 부재, `result` 존재를 확인합니다. 이후 일반 SchemaRouter output JSON Schema validation과 field projection을 수행합니다.

## 범위

현재 일반 request/response JSON-RPC method를 지원합니다. notification, batch request, 장기/streaming RPC lifecycle은 명시적 runtime semantics가 마련될 때까지 보류합니다.

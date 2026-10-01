# OpenAPI

SchemaRouter는 JSON 또는 YAML로 된 일반적인 production-oriented **OpenAPI 3.x subset**을 가져올 수
있습니다.

## Import

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

Adapter는 operation, path/query/header parameter, JSON request body, response schema, local
component reference, read/write classification을 typed contract로 컴파일합니다.

## Same-origin / cross-origin server

같은 origin의 runtime server는 자동 binding할 수 있습니다. 문서가 다른 origin의 server를
가리키는 경우에는 schema만 import하고 실행 권한을 자동으로 넓히지 않습니다.

```python
router.bind_openapi(
    "users_api",
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

## Schema credential과 runtime credential 분리

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    schema_headers={"X-Docs-Token": "..."},
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

`schema_headers`는 runtime API header가 되지 않고, `trusted_headers`는 model-selectable
argument로 노출되지 않습니다.

## JSON root body

Object request body는 가능한 경우 named body parameter로 평탄화합니다. Array, scalar,
nullable root, 일반 `oneOf` / `anyOf`처럼 안전하게 평탄화할 수 없는 schema는 **하나의 typed
`body` parameter**로 유지합니다.

Required root body가 빠지면 network request 전에 fail-closed 됩니다.

## Discriminated request body

Strictly tagged `oneOf`의 discriminator contract는 각 branch가 자체적으로 unique tag를 증명할
때만 인식합니다. Mapping 문자열만 믿어서 local schema contract를 약화시키지 않습니다.

## OpenAPI 3.0 nullable

OpenAPI 3.0의:

```yaml
type: string
nullable: true
```

는 내부에서 다음 JSON Schema 의미로 정규화합니다.

```json
{"type": ["string", "null"]}
```

OpenAPI 3.1은 원래 JSON Schema 표현을 그대로 사용합니다.

## Parameter serialization

기본 지원 범위:

| 위치 | style | 기본 explode |
| --- | --- | ---: |
| path | `simple` | false |
| query | `form` | true |
| header | `simple` | false |

정확하게 emit하지 못하는 `matrix`, `label`, `spaceDelimited`, `pipeDelimited`,
`deepObject` 및 `allowReserved: true`는 조용히 추측하지 않고 compatibility finding으로
fail-closed 처리합니다.

같은 wire name이 path/query/header/body에 중복되면 논리 argument를 분리합니다.

```text
path:id   -> path__id
query:id  -> query__id
header:id -> header__id
body:id   -> body__id
```

## Reference 처리

Local `#/components/...` chain은 planner-side discovery와 runtime validation 모두를 위해
보수적으로 해석합니다.

Cross-document `$ref`는 기본적으로 fetch하지 않습니다. 필요한 경우 trusted caller가 명시적으로
켜야 합니다.

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    openapi_external_refs=True,
)
```

이 경우에도 same-origin, depth, document count, byte budget, redirect limit을 적용합니다.
Cross-origin reference나 unsupported dynamic reference는 fail-closed입니다.

## Nested response field

Response object 안의 nested declared field도 deterministic dotted identity로 노출할 수 있습니다.

```text
data
  band_gap
  density

-> data
-> data.band_gap
-> data.density
```

Array-of-object도 record alignment를 보존하는 `*` path를 사용합니다. Payload sample을 보고
임의 wildcard field를 추론하지 않습니다.

## Runtime response bound

OpenAPI runtime response는 기본 **16 MiB** 상한을 적용한 뒤 decode합니다. 서버가
`Content-Length`를 생략하거나 잘못 보내도 이 상한을 우회하지 못합니다.

## sparse schema 보완

Upstream OpenAPI가 output field를 충분히 선언하지 않았다면 trusted local code가
`amend_capability()`로 semantic ID, unit, field contract를 보완할 수 있습니다. 이 수정은
execution identity나 remote permission을 임의로 바꾸는 수단이 아닙니다.

[MCP의 result contract 보완 예제 →](mcp.md#서버가-공개하지-않는-result-contract-선언)

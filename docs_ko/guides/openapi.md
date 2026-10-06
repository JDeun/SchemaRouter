# OpenAPI

SchemaRouter는 JSON이나 YAML로 작성된 **OpenAPI 3.x의 주요 기능**을 읽어 등록할 수 있습니다.

## Import

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

Adapter는 operation, path/query/header parameter, JSON request body, response schema, local
component reference를 읽고, HTTP method를 바탕으로 읽기/쓰기 성격까지 계약에 기록합니다.

## Same-origin / cross-origin server

OpenAPI 문서와 같은 origin의 server는 자동으로 연결할 수 있습니다. 문서가 다른 origin을
가리키면 schema는 읽되, 그 주소를 자동으로 실행 대상으로 신뢰하지는 않습니다.

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

`schema_headers`는 문서를 읽을 때만 쓰고 runtime API 요청에는 전달하지 않습니다.
반대로 `trusted_headers`는 모델이 선택하거나 수정할 수 있는 argument로 노출하지 않습니다.

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

SchemaRouter가 정확히 직렬화하지 못하는 `matrix`, `label`, `spaceDelimited`,
`pipeDelimited`, `deepObject`, `allowReserved: true`는 임의로 흉내 내지 않습니다.
호환성 검사에서 지원하지 않는 항목으로 표시하고 실행하지 않습니다.

같은 wire name이 path/query/header/body에 중복되면 논리 argument를 분리합니다.

```text
path:id   -> path__id
query:id  -> query__id
header:id -> header__id
body:id   -> body__id
```

## Reference 처리

같은 문서 안의 `#/components/...` reference chain은 planner와 runtime validator가 함께 사용할
수 있도록 해석합니다.

다른 문서를 가리키는 `$ref`는 기본적으로 가져오지 않습니다. 필요할 때만 애플리케이션 코드에서
명시적으로 켭니다.

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

## YAML parser 자원 상한

원격 OpenAPI YAML은 Python 객체를 생성하기 전에 자원 상한을 검사합니다. 기본적으로
**alias 256개**, **anchor 256개**, **composed node 100,000개**, **논리적으로 확장된 node
100,000개**, **중첩 깊이 64단계**를 넘으면 거부합니다. Alias를 여러 단계로 재사용하는
경우에도 논리적 확장량을 계산하므로 작은 원문으로 큰 객체 그래프를 만드는 우회를 막습니다.
순환 alias graph도 결정적으로 거부합니다.

이 상한은 기존 **5 MiB** schema document byte 제한과 post-parse schema complexity 검사에
추가로 적용됩니다. 정상적인 anchor/alias 사용은 상한 안에서 계속 지원하며 JSON ingestion
동작은 변경하지 않습니다.

## Runtime response bound

OpenAPI runtime response는 기본 **16 MiB** 상한을 적용한 뒤 decode합니다. 서버가
`Content-Length`를 생략하거나 잘못 보내도 이 상한을 우회하지 못합니다.

## sparse schema 보완

Upstream OpenAPI가 필요한 output field를 충분히 선언하지 않았다면 애플리케이션 코드에서
`amend_capability()`로 semantic ID, unit, field contract를 보완할 수 있습니다. 다만 이 기능으로
endpoint의 실행 정체성이나 원격 권한을 바꿀 수는 없습니다.

[MCP의 result contract 보완 예제 →](mcp.md#서버가-공개하지-않는-result-contract-선언)

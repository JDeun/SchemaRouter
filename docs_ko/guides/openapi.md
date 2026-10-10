# OpenAPI

SchemaRouter는 JSON이나 YAML로 작성된 **OpenAPI 3.x의 주요 기능**을 읽어 등록할 수 있습니다.

## Import

Adapter는 operation, path/query/header parameter, JSON request body, response schema, local
component reference를 읽고, HTTP method를 바탕으로 읽기/쓰기 성격까지 계약에 기록합니다.

`allOf`로 연결된 객체 속성과 필수 필드는 플래너용으로 평탄화하지만, 원래의 합성 스키마는 런타임 JSON Schema 검증에 남겨 둡니다. `oneOf`·`anyOf` 응답의 조건부 객체 필드는 검색 가능한 출력 필드가 되더라도 원본 스키마로 검증합니다.

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

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

`schema_headers`는 문서를 읽을 때만 쓰고 runtime API 요청에는 전달하지 않습니다.
반대로 `trusted_headers`는 모델이 선택하거나 수정할 수 있는 argument로 노출하지 않습니다.

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    schema_headers={"X-Docs-Token": "..."},
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

## JSON root body

Object request body는 가능한 경우 named body parameter로 평탄화합니다. Array, scalar,
nullable root, 일반 `oneOf` / `anyOf`처럼 안전하게 평탄화할 수 없는 schema는 **하나의 typed
`body` parameter**로 유지합니다.

Required root body가 빠지면 network request 전에 fail-closed 됩니다.

안전하게 평탄화할 수 없는 본문에는 배열, 스칼라, `null`을 포함한 nullable 루트, `oneOf`·`anyOf` 합성이 포함됩니다. SchemaRouter는 전체 값을 원본 스키마로 검증한 뒤 JSON 루트로 그대로 전송합니다. `{"body": ...}` 객체로 감싸거나, JSON `null`을 본문 생략으로 바꾸지 않습니다.

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: array
        items:
          type: string
```

```text
body: array[string]
```

## Discriminated request body

Strictly tagged `oneOf`의 discriminator contract는 각 branch가 자체적으로 unique tag를 증명할
때만 인식합니다. Mapping 문자열만 믿어서 local schema contract를 약화시키지 않습니다.

임의의 `oneOf`·`anyOf`를 평탄화하면 서로 다른 변형의 필드가 합쳐져 잘못된 본문이 될 수 있습니다. 엄격한 discriminator를 인정하려면 `discriminator.propertyName`이 선언되고, 모든 분기가 객체여야 하며, 각 분기는 해당 필드를 필수로 요구하고 고유한 `const` 또는 단일 값 `enum`을 증명해야 합니다. 모델이 제안한 변형도 로컬에서 전체 검증합니다. 임의의 `oneOf`/`anyOf` 본문은 서로 다른 branch의 필드를 합치지 않고 하나의 타입이 지정된 루트 `body` 파라미터로 보존합니다. 플래너에도 원래의 composed `oneOf` 스키마와 discriminator metadata를 전달하고 전체 객체를 원래 JSON Schema로 검증한 뒤, OpenAPI invoker가 객체를 그대로 JSON 요청의 최상위 값으로 전송합니다. `{"body": ...}` 같은 wrapper를 새로 만들지 않습니다. 호출자가 소유한 `ModelQueryAnalyzer`에 연결된 GPT·Gemini·Claude 등 structured-output 모델이 완전한 `body`를 제안할 수 있지만 알 수 없는 인자와 스키마에 맞지 않는 변형은 실행 전에 로컬에서 거부합니다.

```yaml
schema:
  oneOf:
    - $ref: '#/components/schemas/Cat'
    - $ref: '#/components/schemas/Dog'
  discriminator:
    propertyName: kind
```

## OpenAPI 3.0 nullable

OpenAPI 3.0에서는 `type`과 `nullable: true`가 같은 Schema Object에 선언됐을 때 일반 JSON Schema의 `null` 타입을 포함하는 union으로 정규화합니다. 아래 첫 번째 YAML 선언은 두 번째 JSON Schema와 동일한 의미입니다.

OpenAPI 3.1은 원래 JSON Schema 표현을 그대로 사용합니다.

다른 제약도 계속 적용됩니다. 예를 들어 `enum`에 `null`이 없다면 nullable 선언만으로 통과하지 않습니다. 정규화는 component와 제한된 외부 참조에 재귀적으로 적용되지만 examples·default·임의 확장 데이터는 변경하지 않습니다. nullable 객체 루트는 평탄화하지 않습니다.

```yaml
type: string
nullable: true
```

```json
{"type": ["string", "null"]}
```

## Parameter serialization

기본 지원 범위:

| 위치 | 지원 스타일 | 기본 explode | 지원 값 |
| --- | --- | ---: | --- |
| path | `simple` | `false` | scalar, array, object |
| query | `form` | `true` | scalar, array, object |
| header | `simple` | `false` | scalar, array, object |

SchemaRouter가 정확히 직렬화하지 못하는 `matrix`, `label`, `spaceDelimited`,
`pipeDelimited`, `deepObject`, `allowReserved: true`는 임의로 흉내 내지 않습니다.
호환성 검사에서 지원하지 않는 항목으로 표시하고 실행하지 않습니다. 특히 `allowReserved: true` 쿼리 파라미터는 reserved character의 해석을 조용히 변경하지 않도록 거부합니다. 실행 전에 호환성 보고서에서 `parameter_style` 또는 `allow_reserved` finding으로 드러납니다.

같은 wire name이 path/query/header/body에 중복되면 논리 argument를 분리합니다.

```text
path simple array:
  ["a", "b"] -> /a,b

query form array, explode=true:
  ["red", "blue"] -> ?tag=red&tag=blue

query form object, explode=false:
  {"role":"admin","active":true}
  -> ?filter=role,admin,active,true

header simple object, explode=true:
  {"role":"admin","active":true}
  -> X-Meta: role=admin,active=true
```

## Parameter collisions

OpenAPI parameter identity는 name+location입니다. 동일 wire name이 여러 위치에 있으면 distinct logical key를 만듭니다.

Transport는 이 key를 원래 wire name으로 다시 mapping합니다.

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

이 경우에도 same-origin, depth, document count, byte budget, redirect limit을 적용합니다.
Cross-origin reference나 unsupported dynamic reference는 fail-closed입니다.

URL이 현재 읽은 문서와 같은 대상을 가리키면 `./openapi.json#/components/schemas/User` 같은 참조를 로컬 JSON Pointer로 정규화합니다. 다른 문서를 가리키는 참조는 명시적 허용 후에만 동일 출처에서 가져옵니다. 참조 문서의 깊이·개수·총 바이트·개별 문서 크기·리디렉션 수를 각각 제한합니다. 해당 한도는 신뢰하는 애플리케이션 코드에서 `SchemaRouter.from_url()` 또는 `add_url()`의 키워드 인자로 더 낮출 수 있습니다. 명시적으로 외부 참조를 허용한 경우에만 `schema_headers`를 같은 출처의 참조에 재사용합니다. JSON/YAML 참조 문서는 완전히 가져와 JSON Schema resource로 인덱싱하고, 원래 위치의 `$ref`를 로컬 JSON Pointer로 다시 작성해 in-memory bundle로 만듭니다.

같은 출처의 절대·상대 `$id`는 하위 `$ref`의 기준 위치를 바꾸고, 중첩된 `$id`는 이미 가져온 문서 안의 가상 resource로 인덱싱됩니다. `schema.json#User` 같은 정적 `$anchor`도 대상 subschema로 해석됩니다. 최종 runtime bundle에서는 `$id`·`$anchor`를 제거해 외부 참조를 다시 시도하지 않게 합니다.

교차 출처 참조 문서나 `$id` 기준 URI, fragment가 붙은 `$id`, 누락·중복·잘못된 정적 anchor, `$dynamicRef`, `$dynamicAnchor`, `$recursiveRef`, `$recursiveAnchor`, 제한 초과 또는 구조화되지 않은 참조 내용은 **fail-closed**합니다. 동적 JSON Schema scope를 정적 anchor로 잘못 치환하면 검증 의미가 달라질 수 있기 때문에 이 기능은 현재 범위에서 제외합니다.

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    openapi_external_refs=True,
)
```

```text
openapi_ref_max_depth      = 3
openapi_ref_max_documents  = 8
openapi_ref_max_bytes      = 10 MiB
per referenced document    = 5 MiB
redirects per document     = 5
```

## Nested response field

Response object 안의 nested declared field도 deterministic dotted identity로 노출할 수 있습니다.

Array-of-object도 record alignment를 보존하는 `*` path를 사용합니다. Payload sample을 보고
임의 wildcard field를 추론하지 않습니다.

중첩 객체를 발견하면 상위 `data`뿐 아니라 `data.band_gap`, `data.density`처럼 결정적인 점 표기 field ID를 노출합니다. 각각 원본 JSON Schema, 설명, 단위, 원천 경로를 보존합니다. 선택한 중첩 필드의 projected result key도 점 표기 이름을 사용하므로 상위 객체와 충돌하지 않습니다. 재귀 local ref는 순환을 안전하게 차단하며 제한된 범위에서 탐색합니다.

`data[].band_gap`의 원본/결과 경로는 `["data", "*", "band_gap"]`입니다. 선언된 배열의 각 항목을 의미하는 `"*"`는 `data[].band_gap`과 `data[].density`를 서로 대응하는 **동일 레코드**로 묶어 보존합니다. 근거가 없는 응답 예시에서 wildcard field를 추론하지 않습니다. 루트 자체가 `[{id, score}, ...]` 형태의 배열이면 합성 `[].id` 필드가 아니라 `id`, `score` 필드가 제공됩니다.

중첩 출력 필드에는 원본 JSON Schema, 설명, 단위, 원천 경로를 보존합니다. `data[].band_gap`의 `*` 경로는 선언된 배열의 각 레코드를 뜻하며, 선택된 여러 필드가 하나의 레코드에 속한다는 관계를 보존합니다. 페이로드 사례만 보고 wildcard를 추론하지 않습니다. Provider가 선언한 스키마·설명·원본 단위는 그대로 가져옵니다. `semantic_id`, qualifier, canonical unit normalization, source type, license는 신뢰하는 `amend_capability()`를 통해 나중에 붙일 수 있지만 원격 문서의 단위 문자열에서 변환 계수나 의미적 provenance를 추론하지 않습니다.

```text
data
  band_gap
  density
```

```text
data[].band_gap + data[].density
    -> data:
         - {band_gap: ..., density: ...}
         - {band_gap: ..., density: ...}
```

## Current common subset

지원 범위:

- OpenAPI 3.x JSON/YAML
- `paths` operation
- path/query/header parameter와 spec-faithful default simple/form serialization
- object-like JSON body 및 JSON response
- 로컬 컴포넌트·경로 항목 참조 체인
- same-document URI-reference normalization
- explicit enable된 bounded same-origin cross-document `$ref`
- 동일 출처 내 제한된 JSON Schema `$id` 기준 재설정 및 정적 `$anchor` 해석
- same Schema Object에 type이 있는 OpenAPI 3.0 `nullable: true`
- `allOf` object-property/required planner flattening
- runtime composed validation을 유지하는 `oneOf`/`anyOf` response field discovery
- array/scalar/nullable/composed body를 포함한 non-flattenable JSON root-body parameter
- strictly tagged `oneOf` object discriminator recognition
- explicit cross-origin binding
- runtime origin confinement

Dynamic JSON Schema reference/anchor와 automatic planner-side variant selection은 follow-up입니다. Variant request body는 executable root body로 유지하되 flatten하지 않습니다. Response variant field는 projection 가능하지만 actual validated variant에 없는 field는 projected result에서도 absent입니다. Unsupported construct를 추측하지 않습니다.

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

`OpenAPIRemoteInvoker`를 직접 만들 때 신뢰할 수 있는 로컬 코드에서 양의 정수 `max_response_bytes`를 지정해 제한을 변경할 수 있습니다. 너무 큰 한도는 예상치 못한 원격 응답에 대한 보호를 약화합니다.

## sparse schema 보완

Upstream OpenAPI가 필요한 output field를 충분히 선언하지 않았다면 애플리케이션 코드에서
`amend_capability()`로 semantic ID, unit, field contract를 보완할 수 있습니다. 다만 이 기능으로
endpoint의 실행 정체성이나 원격 권한을 바꿀 수는 없습니다.

[MCP의 result contract 보완 예제 →](mcp.md#declare-a-result-contract-the-server-does-not-publish)

공개된 스키마가 단순한 객체로만 응답을 설명하는 경우, 상위 문서를 수정하지 않고도 신뢰할 수 있는 코드에서 필드의 의미 ID와 단위를 선언할 수 있습니다. 허용되는 선언 변경과 금지되는 실행 권한 변경은 아래 예제를 참고하십시오.

```python
router.amend_capability(key, amended)
```

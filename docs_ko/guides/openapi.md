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

Adapter는 operation, path/query/header parameter, JSON request-body property, response schema, local component reference chain, local Path Item reference를 읽고 HTTP method에서 read/write classification을 도출합니다. `allOf`을 통해 도달 가능한 object property/required field는 planner visibility를 위해 flatten하지만 원래 composition은 runtime JSON Schema validation에 유지합니다. response schema의 `oneOf` / `anyOf` variant에서 도달 가능한 object field도 conditional planner-visible output field로 노출하며 원래 composed response schema가 runtime authority입니다.

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

## Typed JSON root request body

Object request body는 가능한 경우 named body parameter로 평탄화합니다. Array, scalar,
nullable root, 일반 `oneOf` / `anyOf`처럼 안전하게 평탄화할 수 없는 schema는 **하나의 typed
`body` parameter**로 유지합니다.

예를 들어 array body:

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

는 다음과 같은 typed parameter가 됩니다:

```text
body: array[string]
```

전체 값이 원래 schema로 로컬 검증된 뒤 JSON root 자체로 전송됩니다. `{"body": ...}`로 감싸지 않으며 JSON `null`도 omitted request가 아니라 literal `null` body로 전송합니다.

Required root body가 빠지면 network request 전에 fail-closed 됩니다.

## Discriminated JSON request body

SchemaRouter는 서로 다른 variant field가 섞여 invalid request가 되는 것을 막기 위해 임의의 `oneOf` / `anyOf` request body를 flatten하지 않고 하나의 typed root `body`로 유지합니다.

예:

```yaml
schema:
  oneOf:
    - $ref: '#/components/schemas/Cat'
    - $ref: '#/components/schemas/Dog'
  discriminator:
    propertyName: kind
```

strictly tagged `oneOf`은 schema가 `discriminator.propertyName`을 선언하고, 모든 branch가 object-like이며 해당 discriminator를 required로 갖고 unique `const` 또는 single-value `enum`으로 제한할 때만 discriminator contract를 인식합니다. planner는 원래 `oneOf` schema와 discriminator metadata를 가진 하나의 parameter를 보며 전체 object는 original composed JSON Schema로 검증됩니다. application-owned GPT/Gemini/Claude 같은 `ModelQueryAnalyzer`가 complete body object를 제안해도 unknown argument와 schema-invalid variant는 실행 전에 로컬에서 거부됩니다. mapping 문자열만으로 local contract를 약화하지 않습니다.

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

다른 constraint도 계속 authoritative합니다. 예를 들어 `enum`에 `null`이 없으면 OpenAPI 3.0 규칙대로 `null`을 거부할 수 있습니다. Normalization은 component schema와 bounded external-reference bundle 안에서 recursive하게 적용하지만 example/default value와 arbitrary extension payload는 rewrite하지 않습니다.

Nullable object request body는 JSON root 자체가 `null`일 수 있으므로 flatten하지 않고 typed root `body`로 유지합니다.

OpenAPI 3.1은 rewrite하지 않으며 `type: ["string", "null"]` 같은 JSON Schema 표현을 사용해야 합니다.

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

예:

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

## Parameter collision

OpenAPI는 parameter를 name과 location의 조합으로 식별합니다. 같은 wire name이 path/query/header/body에 중복되면 논리 argument를 분리합니다.

```text
path:id   -> path__id
query:id  -> query__id
header:id -> header__id
body:id   -> body__id
```

## Local 및 same-document reference

Nested `#/components/...` reference chain은 array item schema와 recursive structure를 포함해 planner-side schema discovery에서 resolve하면서 component root를 runtime JSON Schema validation에 유지합니다.

URL에서 문서를 load한 경우 현재 문서 자체로 resolve되는 URI reference는 local JSON Pointer로 normalize합니다. 예를 들어 loaded resource가 같은 `openapi.json`이면 `./openapi.json#/components/schemas/User`를 local reference로 취급합니다.

다른 문서를 가리키는 `$ref`는 기본적으로 가져오지 않습니다. 필요할 때만 애플리케이션 코드에서
명시적으로 켭니다.

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    openapi_external_refs=True,
)
```

resolver는 entry document origin 안에 머무는 relative/absolute HTTP(S) reference만 따라갑니다. explicit opt-in 뒤에만 `schema_headers`를 재사용하며 recursion depth, unique referenced document, aggregate/per-document bytes, redirect 수를 독립적으로 제한합니다.

기본값:

```text
openapi_ref_max_depth      = 3
openapi_ref_max_documents  = 8
openapi_ref_max_bytes      = 10 MiB
per referenced document    = 5 MiB
redirects per document     = 5
```

Referenced JSON/YAML은 완전히 fetch하여 JSON Schema resource로 index하고 local in-memory bundle로 rewrite한 뒤 동일한 local-ref parser/runtime validator가 사용합니다.

`openapi_external_refs=True`에서는 same-origin absolute/relative `$id` rebasing, nested `$id` virtual resource, static `$anchor`를 지원합니다. rewrite 뒤 `$id`/`$anchor`는 runtime bundle에서 제거하여 두 번째 external-resolution 경로가 생기지 않게 합니다.

cross-origin document/base URI, fragment를 가진 `$id`, missing/duplicate/invalid static anchor, `$dynamicRef`/`$dynamicAnchor`/`$recursiveRef`/`$recursiveAnchor`, resource-limit exhaustion, unstructured referenced content는 fail closed합니다.

## Nested response-field discovery

Response object 안의 nested declared field도 deterministic dotted identity로 노출할 수 있습니다. 기존 top-level field도 유지하며 nested field는 declared JSON Schema, description, unit metadata, source path를 보존합니다. Projected result key는 dotted field name을 사용하므로 parent object 선택과 충돌하지 않습니다.

```text
data
  band_gap
  density

-> data
-> data.band_gap
-> data.density
```

Recursive local reference는 bounded/cycle-safe하게 처리합니다. Declared array-of-object도 record alignment를 보존하는 item field를 노출합니다. 예를 들어 `data[].band_gap`은 source/result path `["data", "*", "band_gap"]`를 사용하며 `*`는 각 declared array item을 뜻합니다. Observed payload에서 wildcard field를 추론하지 않습니다.

여러 item field 선택은 다음처럼 source record를 보존합니다:

```text
data[].band_gap + data[].density
    -> data:
         - {band_gap: ..., density: ...}
         - {band_gap: ..., density: ...}
```

 여러 item field를 함께 선택해도 각 source record의 sibling 관계를 유지합니다. root response array는 synthetic `[].id` 같은 이름을 만들지 않고 item field 자체를 노출합니다. Payload sample을 보고 임의 wildcard field를 추론하지 않습니다.

provider-declared JSON Schema, description, source unit은 가능한 경우 import하지만 semantic ID, qualifier, canonical-unit normalization, source type, licence는 trusted `amend_capability()`을 통해 나중에 붙일 수 있습니다. conversion factor나 semantic provenance를 unit string/remote prose에서 추론하지 않습니다.

## 현재 공통 지원 범위

지원 범위에는 OpenAPI 3.x JSON/YAML, `paths` operation, 기본 `simple`/`form` parameter serialization, object-like JSON body, JSON response, local reference chain, same-document URI normalization, opt-in same-origin external-ref bundling, bounded `$id`/`$anchor`, OpenAPI 3.0 nullable normalization, `allOf` flattening, response `oneOf`/`anyOf` field discovery, non-flattenable typed root body, strict discriminator, explicit cross-origin binding, runtime origin confinement이 포함됩니다.

Dynamic JSON Schema reference/anchor와 automatic planner-side schema-variant selection은 후속 작업입니다. Variant request body는 executable typed root body이더라도 unflattened 상태를 유지합니다. Response variant field는 projection 대상으로 선택할 수 있지만 실제 validated response variant에 없는 field는 projected result에서도 단순히 빠집니다. Unsupported construct는 추측하지 않습니다.

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

OpenAPI runtime response는 기본 **16 MiB** 상한을 적용한 뒤 decode합니다. 서버가 `Content-Length`를 생략하거나 잘못 보내도 이 상한을 우회하지 못합니다.

`OpenAPIRemoteInvoker`를 직접 만들 때 trusted local code는 `max_response_bytes`에 더 작거나 큰 양의 정수를 지정할 수 있습니다. endpoint contract에 맞는 상한을 유지해야 하며 지나치게 큰 값은 예상 밖 대형 response에 대한 보호를 약화합니다.

## sparse schema 보완

Upstream OpenAPI가 필요한 output field를 충분히 선언하지 않았다면 애플리케이션 코드에서 다음처럼 보완할 수 있습니다:

```python
router.amend_capability(key, amended)
```

`amend_capability()`로 semantic ID, unit, field contract를 보완할 수 있습니다. 다만 이 기능으로
endpoint의 실행 정체성이나 원격 권한을 바꿀 수는 없습니다.

[MCP의 result contract 보완 예제 →](mcp.md#서버가-공개하지-않는-result-contract-선언)

# Adapter 작성

Adapter는 core planner, registry, policy, executor를 변경하지 않고 구조화된 capability source를 SchemaRouter에 연결합니다.

## SourceAdapter contract

Source adapter는 안정적인 `kind`, discovery `priority`, 하나의 async load method를 가집니다:

```python
from schemarouter import (
    AdapterContext,
    AdapterLoadResult,
    DiscoveryProfile,
    RefreshProfile,
    SourceAdapter,
)


class MyAdapter:
    kind = "my_protocol"
    priority = 50
    discovery = DiscoveryProfile(
        activity="passive",
        http_methods=("GET",),
    )
    refresh = RefreshProfile(
        mode="url",
        source_key="source_url",
        source_location="metadata",
    )

    async def load(
        self,
        context: AdapterContext,
    ) -> AdapterLoadResult | None:
        ...
```

Auto discovery 중 source를 인식하지 못하면 `None`을 반환합니다. 지원하는 source라면 `AdapterLoadResult(tool=..., invoker=...)`를 반환합니다.

Discovery profile은 SchemaRouter가 `kind="auto"`를 시도할 때 `load()`가 수행할 수 있는 작업을 신뢰된 local code가 선언한 것입니다. Protocol session을 열지 않는 제한된 GET/HEAD schema read에만 `activity="passive"`를 사용합니다. GraphQL introspection POST, MCP handshake 및 유사 상호작용은 `activity="active"`입니다.

`DiscoveryProfile`이 없는 adapter도 명시적 `kind`로 사용할 수 있지만 보수적으로 active로 취급되어 기본 auto discovery에서는 건너뜁니다. Active auto-probing이 필요한 application은 `allow_active_probes=True`를 명시해야 하며 remote content는 이 flag를 활성화할 수 없습니다.

Schema refresh/watch는 별도의 trusted-local capability입니다. Plugin은 `RefreshProfile`로 명시적으로 참여해야 하며, ingest할 수 있다는 사실만으로 **refresh 가능해지지는 않습니다**.

일반적인 URL 기반 structured source에는 다음과 같이 설정합니다:

```python
refresh = RefreshProfile(
    mode="url",
    source_key="source_url",
    source_location="metadata",
    http_validators=False,
)
```

선언된 `source_key`는 adapter가 반환한 `ToolSpec`에 저장한 stable credential-free provenance를 가리켜야 합니다. SchemaRouter는 reinspection에 adapter의 일반 `load(context)` path를 재사용한 뒤 built-in과 동일한 schema-diff/CAS rule을 적용합니다. `RefreshProfile`을 생략하거나 기본 unsupported profile을 사용하는 plugin은 ingest/execution은 가능하지만 refresh/watch할 수 없습니다.

`identity_metadata_keys`와 `identity_execution_keys`는 source identity에 non-secret representation 또는 transport qualifier를 추가할 수 있습니다. Credential처럼 보이는 key name은 거부됩니다. Refresh identity metadata에는 Authorization header, cookie, token, API key, password, client secret, factory object를 절대 포함하지 마십시오.

Built-in OpenAPI/OpenRPC/OData는 conditional HTTP-validator support를 선언합니다. Plugin은 URL refresh path가 SchemaRouter의 bounded `schema_validators` contract를 준수할 때만 `http_validators=True`를 설정해야 합니다. MCP의 bound stdio/custom transport는 명시적인 special trusted-state mode로 유지되며 remote metadata에서 추론하지 않습니다.

## Adapter 등록

```python
router = SchemaRouter()
router.register_adapter(MyAdapter())

tool = await router.add_url(
    "https://example.com/capability",
    kind="my_protocol",
)
```

Application은 `AdapterRegistry`를 직접 구성해 `SchemaRouter`에 주입할 수도 있습니다.

## Third-party adapter 배포

설치된 package는 `schemarouter.adapters` entry-point group을 통해 adapter를 노출할 수 있습니다:

```toml
[project.entry-points."schemarouter.adapters"]
my_protocol = "my_package.adapter:MyAdapter"
```

SchemaRouter는 발견된 plugin을 자동 import하지 않습니다. Application이 plugin entry-point name을 명시적으로 allowlist해야 합니다:

```python
router.load_adapter_plugins(allowlist={"my_protocol"})
```

`discover_adapter_plugins()`를 사용하면 plugin code를 import하지 않고 metadata를 inspect할 수 있습니다. Unknown allowlisted name은 plugin load 전에 실패합니다. 전체 trust model은 [Third-party adapter plugins](guides/adapter-plugins.md)를 참고하십시오.

## Adapter의 책임

Schema adapter는 다음을 반환해야 합니다:

- a `ToolSpec`;
- 하나 이상의 `EndpointSpec` object;
- declared `ParameterSpec` object;
- field가 projectable한 경우 declared `FieldSpec` object;
- source가 제공하는 경우 input/output JSON Schema;
- remote에서 온 경우 untrusted로 표시한 descriptive metadata;
- invoker가 remote trust boundary를 넘는 capability에는 `tool.remote=True`;
- 전송 또는 실행 동작에 영향을 미쳐 스키마 지문에 포함해야 하는 JSON 호환 값을 위한 `ToolSpec.execution_metadata` / `EndpointSpec.execution_metadata`

일반 transport adapter는 다음 signature와 호환되는 invoker를 제공할 수 있습니다:

```python
invoker(endpoint_name: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]
```

Transport에서 planner가 선택한 field가 필요한 protocol은 대신 다음을 구현할 수 있습니다:

```python
invoke_call(call: ToolCall) -> Any | Awaitable[Any]
```

OPTIMADE adapter는 이 call-aware path를 사용해 `ToolCall.fields`를 `response_fields`로 변환합니다. 향후 GraphQL/OData adapter도 core executor에 protocol logic을 넣지 않고 selection set이나 `$select`에 동일한 mechanism을 사용할 수 있습니다.

Invoker는 `RegistryExecutor.bind()`를 통해 binding되므로 tool fingerprint drift를 계속 강제할 수 있습니다.

## Trust boundary

Adapter는 다음 동작을 해서는 안 됩니다:

- remote annotation을 local mutation/destructive permission으로 변환;
- API key, cookie, bearer token 등 runtime secret을 model-selectable parameter로 노출;
- endpoint를 unapproved origin으로 조용히 따라감;
- executor 뒤에서 invalid model value를 schema-valid value로 강제 변환;
- SchemaRouter input/output validation 생략;
- planning에서 remote service를 직접 호출.

원격 어댑터는 `tool.remote = True`를 설정하거나 `ToolSpec(remote=True, ...)`로 생성하여 분류되지 않은 부작용에도 정책 검사가 적용되도록 해야 합니다. 일반 `metadata`는 설명 목적으로만 사용하며, 호출기가 실행 출처·전송 대상·요청 인코딩 또는 다른 실행 의미를 결정하는 데 읽어서는 안 됩니다.

Invoker에 adapter-specific runtime value가 필요하면 fingerprint 대상인 `execution_metadata`에 넣습니다. 예:

```python
tool = ToolSpec(
    name="graphql",
    remote=True,
    execution_metadata={
        "adapter": "graphql",
        "approved_base_url": approved_base_url,
    },
    endpoints=[
        EndpointSpec(
            name="query",
            execution_metadata={"selection_mode": "typed"},
            # ...
        )
    ],
)
```

어떤 메타데이터에도 인증 정보를 넣지 마세요. 비밀 정보는 신뢰된 호출기 객체에만 유지합니다. 탐색·스키마 URL은 출처 정보이며 자동으로 실행 대상 식별자가 되지 않습니다. 호출기가 실제로 사용하지 않는 URL이라면 설명 정보로만 유지하세요. URL이 `execution_metadata`에 포함된다면 인증 정보가 없는 안정적인 주소를 사용하고, 쿼리·프래그먼트를 이용한 인증은 신뢰된 전송 설정에서 관리해야 합니다.

## Schema fidelity

사용 가능한 가장 풍부한 source schema를 보존하십시오. Flattened field는 planning/projection에 유용할 수 있지만 full input/output schema는 runtime validation을 위해 유지해야 합니다.

지원하지 않는 construct는 추측하지 말고 metadata로 보존하거나 명시적으로 거부해야 합니다.

### Field contract 적합성

Planner-visible field를 노출하는 모든 adapter는 wire protocol이 달라도 동일한 `FieldSpec` contract를 보존해야 합니다.

각 declared field에 대해 source가 실제 제공하는 정보를 보존하십시오:

- datatype/shape를 위한 `json_schema`;
- `description`과 conservative alias;
- validated provider/source location을 위한 `path`;
- downstream projection key가 다를 때 `result_path`;
- source contract가 명시적으로 선언한 경우에만 `unit`;
- source identity semantic이 알려진 경우에만 `identifier`;
- adapter가 신뢰성 있게 명시할 수 있을 때 `source_type`.

Nested object field는 adapter가 record alignment를 깨뜨리지 않고 project할 수 있을 때만 추가 planner-visible field로 노출할 수 있습니다. Parent field도 동시에 유지될 수 있으므로 nested field는 서로 겹치지 않는 `result_path`를 사용해야 합니다.

배열 항목을 탐색할 때는 신뢰할 수 있는 원본 스키마에 배열 항목 스키마가 선언된 경우에만
명시적인 `"*"` 경로 세그먼트를 사용합니다. 예를 들어 `["results", "*", "title"]`은
`results[].title`로 노출됩니다. 여러 항목 필드를 선택했을 때 원래 레코드의 배열
인덱스에 맞춰 합쳐지도록, 일반적으로 `result_path`에도 동일한 와일드카드를
지정해야 합니다. 최상위 배열은 암묵적으로 탐색하므로 `"*"`로 시작하지 않습니다.

Example payload만 inspect해서 wildcard field를 추가하지 마십시오. Array/item contract는 structured schema metadata 또는 trusted local adapter code에서 와야 합니다.

Semantic ID, unit-normalization dimension/conversion, qualifier, licence, provenance는 trusted contract입니다. Authoritative structured source에서만 import하거나 `amend_capability()` 같은 trusted local enrichment를 통해 추가하십시오. 임의 remote description이나 model에서 추론해서는 안 됩니다.

Third-party adapter는 이러한 fidelity를 책임집니다. SchemaRouter는 반환된 `ToolSpec`을 validate하지만 adapter 반환 후 plugin의 private payload schema를 몰래 crawl하거나 rewrite하지 않습니다.

## Custom registry

Application은 `ToolRegistry`의 어떤 structural implementation도 제공할 수 있습니다:

```python
from schemarouter import SchemaRouter, ToolRegistry

registry: ToolRegistry = MyPersistentRegistry(...)
router = SchemaRouter(registry=registry)
```

Registry는 monotonic version과 current tool/endpoint lookup semantic을 제공해야 합니다. Read method는 detached snapshot 또는 immutable equivalent를 반환해야 하며 caller가 versioned write 없이 stored schema를 변경할 수 없어야 합니다. Persistent implementation은 concurrency control과 atomic replacement를 책임집니다.

## Conformance 요구사항

새 adapter는 다음 항목을 테스트해야 합니다:

- 명시적인 도구 종류 지정과 자동 검색의 동작;
- 등록 충돌 및 네임스페이스;
- 스키마 지문의 변경;
- 필수 매개변수와 선언되지 않은 매개변수;
- 잘못된 입력값;
- 잘못된 원시 출력값;
- 오래된 호출기 바인딩;
- 도구 수준의 출처·전송 방식이 변경된 뒤 무효화되지 않은 계획;
- 실행 의미를 변경하지 않는 일반 메타데이터 수정;
- 인증정보 분리;
- 데이터 변경 및 파괴적 작업 정책;
- 프로토콜이 서버 측 프로젝션을 지원하는 경우 선택된 필드의 전파;
- 중첩 필드가 노출된 경우 객체의 원본 경로와 결과 경로의 충실도;
- 변환 계수를 추론하지 않고 원본 단위를 유지하는지 여부;
- 부모 필드 질의가 모든 중첩 하위 필드를 암묵적으로 선택하지 않는지 여부;
- 배열 항목 와일드카드 경로가 원본 레코드의 인덱스 정렬을 유지하며 응답 예시에서 추론되지 않는지 여부;
- 의미 식별자, 정규화·차원, 한정자, 원본 유형 및 라이선스 정보를 신뢰할 수 있는 경로에서 보강하는지 여부;
- 관련된 전송 방식별 출처·리디렉션 동작.


## Canonical result path

Provider response key가 local semantic field name과 다르면 local field identity를 안정적으로 유지하고 provider source path와 downstream result path를 분리하십시오:

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    path=["_provider_specific_elasticity"],
    result_path=["elastic_modulus"],
)
```

`path`는 검증된 제공자 응답에서 SchemaRouter가 값을 읽을 위치를 나타냅니다.
`result_path`는 투영된 값을 `ToolResult.data`의 어느 위치에 기록할지 나타냅니다.
`result_path`를 생략하면 기존 동작이 유지되며, 원본에서 값을 읽는 경로를
출력 데이터의 형태에도 그대로 사용합니다.

이를 통해 여러 provider/access contract가 서로 다른 wire schema를 노출하면서 downstream context는 provider-neutral하게 유지할 수 있습니다.


## Scientific datatype 및 unit contract

Scientific quantity를 노출하는 adapter는 source contract가 제공하는 경우 raw value schema와 정확한 provider source unit을 모두 보존해야 합니다.

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    json_schema={"type": "number"},
    unit="GPa",
    unit_normalization=UnitNormalizationSpec(
        dimension="pressure",
        canonical_unit="Pa",
        scale=1e9,
    ),
)
```

`FieldSpec.unit`은 제공자나 데이터 출처가 선언한 단위입니다. 선택적 `unit_normalization`은 신뢰된 로컬 코드가 정확한 아핀 변환 계약을 가진 경우에만 지정할 수 있습니다:

```text
canonical_value = source_value * scale + offset
```

SchemaRouter는 단위 레이블, SI 접두사, 표기 또는 모델 출력에서 단위 변환 계수를 추론하지 않습니다. 단위 기호는 대소문자와 문장부호를 구분합니다. `nm`, `GPa`, `degC` 같은 원격 레이블은 신뢰된 어댑터나 애플리케이션이 변환 규칙을 선언하기 전까지 설명 정보일 뿐입니다.

내장 OpenAPI 및 MCP 어댑터는 인식된 스키마 주석인 `x-ucum-unit`, `x-unit`,
`unit`을 원본 단위 레이블로 보존합니다. 이 문자열만으로
`UnitNormalizationSpec`을 생성하지는 **않습니다**. OPTIMADE는 기존과
마찬가지로 제공자가 선언한 단위를 스키마 어댑터를 통해 보존합니다.

단위 정규화에는 숫자 스칼라 또는 재귀적으로 숫자 배열을 나타내는 스키마가
필요합니다. 이는 `FieldSpec.json_schema` 또는 엔드포인트의 원시
`output_schema`에서 제공할 수 있습니다. 필드 수준 스키마와 엔드포인트
원시 스키마가 모두 동일한 값을 기술한다면 데이터 타입의 형태가 호환되어야 합니다.
실행 시에는 필드 수준 스키마를 강제하므로, 제공자의 느슨한 응답 스키마를 이용해
더 엄격한 로컬 필드 계약을 우회할 수 없습니다.

제공자 간 자동 폴백에서 단위가 있는 필드는 두 경로 모두에 명시적인 데이터 타입
계약이 있어야 합니다. 단위를 알지만 데이터 타입을 모르는 경우에는 자동 대체에
충분한 근거가 되지 않습니다. 폴백에는 의미적 호환성, 결과 데이터 타입 호환성,
그리고 다음 조건 중 하나가 필요합니다.

- 정확히 같은 출처 단위 또는
- 물리 차원 `dimension`과 기준 단위 `canonical_unit`에 대해 명시적으로 일치하는 정규화 계약

Unit은 optional입니다. Text/document/search field는 일반적으로 `unit=None`을 사용하며 abstract, snippet, title, prose 같은 string에는 unit metadata가 필요하지 않습니다.


### Unit을 생략해야 하는 경우

Field가 scientific source에서 왔다는 이유만으로 unit을 붙이지 마십시오. Unit은 provider category가 아니라 value contract에 속합니다.

대표적인 unitless field는 다음과 같습니다:

- 논문 제목·초록·본문
- 웹 검색 요약과 URL
- 재료 이름과 식별자
- 범주형 레이블, 대칭 기호 및 자유 형식 메모
- 출처·라이선스·소스 문자열

예:

```python
FieldSpec(
    name="abstract",
    semantic_id="document_text",
    json_schema={"type": "string"},
    unit=None,  # optional; this is also the default
)
```

필드가 물리량 또는 수치를 나타내고 출처 계약에서 해당 단위를 실제로 정의한 경우에만 단위를 선언해야 합니다. 단위를 모르면 추측하지 말고 설정하지 않은 상태로 두세요.


### Record별 동적 unit

현재 필드 계약은 하나의 `FieldSpec`에 선언된 원본 단위가 하나라고 가정합니다.
제공자가 레코드마다 같은 필드에 서로 다른 단위 레이블을 반환할 수 있다면
SchemaRouter가 실행 시 수신한 문자열만으로 변환 방식을 추론하게 해서는 안 됩니다.

Prefer one of these approaches:

- 제공자의 응답이 SchemaRouter에 전달되기 전에 신뢰할 수 있는 어댑터에서
  하나의 고정 원본 단위 또는 기준 단위로 정규화합니다. 또는
- 단위 의미가 안정적으로 보장되는 별도의 로컬 필드·접근 계약을 노출합니다.

For example, a payload shaped like:

```json
{"value": 130, "unit": "GPa"}
```

실행 시 수신한 문자열에 `GPa`가 적혀 있다는 이유만으로 변환해서는 안 됩니다.
변환 관계는 신뢰할 수 있는 로컬 설정에서 정의해야 합니다. 동적 단위 계약이
명시적으로 지원되기 전까지는 레코드별로 달라지는 단위의 해석을 범용
SchemaRouter 실행 코어 밖에서 처리해야 합니다.


### 무차원 numeric quantity

수치형 과학 데이터에도 단위가 없을 수 있습니다. 푸아송비, 확률, 정규화 점수 및 기타 무차원 계수에 임의의 단위를 만들어서는 안 됩니다.

```python
FieldSpec(
    name="poisson_ratio",
    semantic_id="poisson_ratio",
    json_schema={"type": "number"},
    unit=None,
)
```

단위가 없더라도 이는 타입이 지정된 숫자 계약에 해당합니다. 제공자 간 폴백은
호환되는 다른 무단위 숫자 필드를 찾을 수 있지만, 단위가 있는 물리량을
무단위 값으로(또는 그 반대로) 조용히 대체하지는 않습니다.


## 신뢰된 parameter alias

서로 다른 제공자·접근 계약은 같은 논리적 입력을 다른 로컬 인수 이름으로 받을 수 있습니다. `ParameterSpec.aliases`는 신뢰된 키 동등성에만 사용하세요:

```python
ParameterSpec(
    name="chemical_formula",
    aliases=["formula"],
    required=True,
)
```

A request argument `{"formula": "Si"}` may then compile to
`{"chemical_formula": "Si"}` for that endpoint.

Alias routing은 제한적으로 동작합니다:

- 매개변수 이름이 정확히 일치하면 항상 이를 우선합니다;
- 별칭은 키의 이름만 바꾸며 값 자체는 변경하지 않고 복사합니다;
- 하나의 별칭이 여러 매개변수를 가리킬 수 있으면 임의로 선택하지 않습니다;
- 여러 별칭이 한 매개변수에 경쟁적으로 매핑되더라도 임의로 선택하지 않습니다;
- 폴백 후보는 각자 자신의 매개변수 계약에 따라 인수를 독립적으로 구성합니다.

`aliases`는 값을 변환하는 언어가 아닙니다. 다음과 같은 키 별칭은 유효합니다:

```text
formula="Si" -> chemical_formula="Si"
```

하지만 SchemaRouter는 다음과 같은 값 변환을 일반적으로 자동 생성하지 않습니다:

```text
formula="Si" -> filter='chemical_formula_reduced="Si"'
```

프로토콜별 표현식, 타입 강제 변환, 제공자 전용 질의 언어 구성은 신뢰할 수 있는
어댑터 또는 애플리케이션 코드에서 처리해야 합니다. `wire_name`은 선언된
매개변수의 직렬화 경계를 나타내며 의미적 별칭과 구별됩니다.

어댑터는 임의의 원격 설명이나 모델 출력으로부터 신뢰된 별칭을 추론해서는 안 됩니다. 원격 스키마는 이름을 설명할 수 있지만 두 인수 키의 의미적 동등성은 로컬 코드가 결정합니다.


## Scientific qualifier는 정확한 local contract

제공자 필드에 과학적 비교 가능성에 영향을 미치는 고정된 문맥적 의미가 있다면 어댑터는 `FieldSpec.qualifiers`로 이를 보존할 수 있습니다.

```python
FieldSpec(
    name="youngs_modulus",
    semantic_id="elastic_modulus",
    json_schema={"type": "number"},
    unit="GPa",
    qualifiers={
        "temperature": "300 K",
        "orientation": "[100]",
    },
)
```

필드 계약 전체에 고정되어 있고 출처를 신뢰할 수 있는 한정자만 선언합니다.
레코드마다 달라지는 임의 메타데이터를 이 맵에 복사해서는 안 됩니다.
조건이 레코드별로 달라진다면 일반 반환 필드로 유지하거나 먼저 신뢰할 수 있는
애플리케이션·어댑터 코드에서 제공자 데이터를 정규화해야 합니다.

한정자의 키와 값은 비어 있으면 안 되며 앞뒤 공백이 없어야 합니다.
값은 정확하게 비교되는 불투명한 태그입니다. SchemaRouter는 한정자 문자열에서
단위 변환, 동의어 확장 또는 자연어 추론을 수행하지 않습니다.

이렇게 하면 SchemaRouter를 과학 온톨로지나 질의 언어 엔진으로 확장하지 않고도 한정자가 보수적인 폴백 안전성 검증에 도움이 됩니다.

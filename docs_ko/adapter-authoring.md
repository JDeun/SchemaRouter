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
- `ToolSpec.execution_metadata` / `EndpointSpec.execution_metadata` for JSON-safe values that
  alter transport/runtime behavior and therefore must participate in fingerprints.

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

Remote adapter는 `tool.remote = True`를 설정하여 unclassified side effect가 계속 policy-gated되도록 해야 합니다. Ordinary `metadata` is descriptive only and must
not be read by an invoker to decide execution origin, transport target, request encoding, or other
runtime semantics.

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

어느 metadata에도 credential을 넣지 마십시오. Secret은 신뢰된 invoker object에만 유지합니다.
Discovery/schema URL은 provenance이며 자동으로 runtime identity가 되지 않습니다. Invoker가 실제로 그 URL을 호출하지 않는다면 descriptive 상태로 유지하십시오. If a URL is part of `execution_metadata`, require a stable,
credential-free form and keep query/fragment authentication in trusted transport configuration.

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

Array-item traversal uses an explicit `"*"` path segment only when the authoritative source schema
declares an array item schema. For example, `["results", "*", "title"]` is exposed as
`results[].title`. The same wildcard should normally appear in `result_path` so several selected
item fields merge back into the original record structure by array index. Root arrays are traversed
implicitly and do not start with `"*"`.

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

- explicit-kind and auto-discovery behavior;
- registration collisions and namespaces;
- schema fingerprint changes;
- required and undeclared parameters;
- invalid input values;
- invalid raw output values;
- stale invoker bindings;
- stale plans after tool-level origin/transport changes;
- ordinary metadata changes not altering execution semantics;
- credential separation;
- mutation/destructive policy;
- selected-field propagation when the protocol supports server-side projection;
- nested object path/result-path fidelity when nested fields are exposed;
- source-unit preservation without inferred conversion factors;
- parent-field queries not implicitly selecting every nested descendant;
- array-item wildcard paths preserving source record alignment and never being inferred from payload examples;
- trusted enrichment of semantic IDs, normalization/dimension, qualifiers, source type and licence;
- transport-specific origin/redirect behavior where relevant.


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

`path` describes where SchemaRouter reads the value from the validated provider response.
`result_path` describes where the projected value is written in `ToolResult.data`. If
`result_path` is omitted, existing behavior is preserved and the source projection path is also
used as the output shape.

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

`FieldSpec.unit` is the provider/source unit. `unit_normalization` is optional and must only be
populated when trusted local code has an exact affine conversion contract:

```text
canonical_value = source_value * scale + offset
```

SchemaRouter는 unit label, SI prefix, spelling, model output에서 conversion factor를 추론하지 않습니다. Unit symbol은 대소문자와 punctuation을 구분합니다. A remote label such as `nm`, `GPa`,
or `degC` is descriptive until a trusted adapter/application declares the conversion.

The built-in OpenAPI and MCP adapters preserve recognized schema annotations
`x-ucum-unit`, `x-unit`, and `unit` as the source-unit label. They do **not** create a
`UnitNormalizationSpec` from those strings. OPTIMADE continues to preserve provider-declared
units through its schema adapter.

Unit normalization requires a numeric scalar or recursively numeric-array schema, supplied either
by `FieldSpec.json_schema` or by the endpoint raw `output_schema`. If both field-level and raw
endpoint schemas describe the value, their datatype shapes must be compatible. Field-level schemas
are enforced at execution time, so a loose provider response schema cannot bypass a stronger local
field contract.

For automatic cross-provider fallback, unit-bearing fields require an explicit datatype contract on
both routes. Unknown datatype + known unit is insufficient evidence for automatic substitution.
Fallback requires semantic compatibility plus compatible result datatype and either:

- the same exact source unit; or
- explicit matching physical `dimension` and `canonical_unit` normalization contracts.

Unit은 optional입니다. Text/document/search field는 일반적으로 `unit=None`을 사용하며 abstract, snippet, title, prose 같은 string에는 unit metadata가 필요하지 않습니다.


### Unit을 생략해야 하는 경우

Field가 scientific source에서 왔다는 이유만으로 unit을 붙이지 마십시오. Unit은 provider category가 아니라 value contract에 속합니다.

대표적인 unitless field는 다음과 같습니다:

- paper titles, abstracts, and full text;
- web-search snippets and URLs;
- material names and identifiers;
- categorical labels, symmetry symbols, and free-form notes;
- provenance/license/source strings.

예:

```python
FieldSpec(
    name="abstract",
    semantic_id="document_text",
    json_schema={"type": "string"},
    unit=None,  # optional; this is also the default
)
```

A unit should be declared only when the field represents a physical/numeric quantity and the source
contract actually defines that unit. If the unit is unknown, leave it unset rather than guessing.


### Record별 동적 unit

The current field contract assumes one declared source unit for a `FieldSpec`. If a provider can
return different unit labels for the same field on different records, do not let SchemaRouter infer
conversion behavior from those runtime strings.

Prefer one of these approaches:

- normalize the provider response inside a trusted adapter into one stable source/canonical unit
  before it reaches SchemaRouter; or
- expose separate locally declared field/access contracts whose unit semantics are stable.

For example, a payload shaped like:

```json
{"value": 130, "unit": "GPa"}
```

must not be converted merely because the runtime string says `GPa`. The conversion relationship
remains trusted local configuration. Until an explicit dynamic-unit contract exists, row-dependent
unit interpretation should remain outside the generic SchemaRouter execution core.


### 무차원 numeric quantity

Numeric scientific data can also be unitless. Do not invent a unit for dimensionless quantities
such as a Poisson ratio, probability, normalized score, or other dimensionless coefficient.

```python
FieldSpec(
    name="poisson_ratio",
    semantic_id="poisson_ratio",
    json_schema={"type": "number"},
    unit=None,
)
```

This remains a typed numeric contract even though the unit is absent. Cross-provider fallback may
match another compatible unitless numeric field, but it will not silently substitute a unit-bearing
quantity for a unitless one (or vice versa).


## 신뢰된 parameter alias

Different provider/access contracts can accept the same logical input under different local
parameter names. Use `ParameterSpec.aliases` only for trusted key equivalence:

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

- exact parameter names always win;
- aliases only rename keys and copy values unchanged;
- if one supplied alias can target multiple parameters, SchemaRouter does not guess;
- if multiple supplied aliases compete for one parameter, SchemaRouter does not guess;
- fallback candidates compile arguments independently against their own parameter contracts.

`aliases` are not a value transformation language. For example, this is valid:

```text
formula="Si" -> chemical_formula="Si"
```

but SchemaRouter does not generically synthesize:

```text
formula="Si" -> filter='chemical_formula_reduced="Si"'
```

Protocol expressions, coercions, and provider-specific query-language construction belong in
trusted adapter/application code. `wire_name` remains the serialization boundary for a declared
parameter and is distinct from semantic aliases.

Adapters must not infer trusted aliases from arbitrary remote descriptions or model output. Remote
schemas may describe names, but local code decides whether two argument keys are semantically
equivalent.


## Scientific qualifier는 정확한 local contract

When a provider field has a fixed contextual meaning that affects scientific comparability, adapters
may preserve that context with `FieldSpec.qualifiers`.

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

Only declare qualifiers that are fixed and trusted for the field contract. Do not copy arbitrary
per-record metadata into this map. If a condition varies per record, keep it as an ordinary returned
field or normalize the provider data in trusted application/adapter code first.

Qualifier keys and values must be non-empty and have no surrounding whitespace. Their values are
exact opaque tags; SchemaRouter does not perform unit conversion, synonym expansion, or natural
language inference inside qualifier strings.

This makes qualifiers suitable for conservative fallback safety without turning SchemaRouter into a
scientific ontology or query-language engine.

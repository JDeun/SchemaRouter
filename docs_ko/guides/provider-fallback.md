# Provider-aware access fallback

하나의 information provider가 동일한 underlying dataset을 여러 access path로 제공할 수 있습니다.

예를 들어 materials database는 다음을 제공할 수 있습니다:

- native REST/OpenAPI API
- OPTIMADE endpoint
- Python client 또는 local wrapper

각 path는 authentication, availability, query parameter, response field, rate limit, deployment dependency가 다를 수 있습니다. SchemaRouter는 이를 하나의 logical `provider`를 공유할 수 있는 별도 `ToolSpec` contract로 모델링합니다.

## Provider와 access identity

```python
api_tool = ToolSpec(
    name="mp_api",
    provider="materials_project",
    access_mode="openapi",
    # ...
)

optimade_tool = ToolSpec(
    name="mp_optimade",
    provider="materials_project",
    access_mode="optimade",
    # ...
)
```

`provider`는 **누가 정보를 소유/제공하는지**를 나타냅니다.
`access_mode`는 **이 contract가 어떤 방식으로 정보에 접근하는지**를 나타냅니다.

두 값 모두 fingerprinted tool contract의 일부입니다.

URL과 Python registration API는 동일한 identity를 받습니다:

```python
await router.add_url(
    openapi_schema_url,
    kind="openapi",
    name="mp_api",
    provider="materials_project",
    access_mode="openapi",
)

await router.add_url(
    optimade_base_url,
    kind="optimade",
    name="mp_optimade",
    provider="materials_project",
    access_mode="optimade",
)

router.add_callable(
    mp_summary_search,
    name="mp_python",
    provider="materials_project",
    access_mode="python",
)
```

## 제한된 fallback 컴파일

fallback은 opt-in이며 기본적으로 비활성화됩니다.

```python
from schemarouter import PlanRequest

request = PlanRequest(
    query="Si band gap",
    arguments={"formula": "Si"},
    preferred_tools=["mp_api"],
    fallback_scope="cross_provider",
    max_fallbacks=3,
)

plan = router.plan(request)
```

scope는 다음과 같습니다:

- `disabled`: automatic fallback 없음
- `same_provider`: 동일한 명시적 non-empty provider ID를 가진 precompiled alternative만 허용
- `cross_provider`: same-provider alternative를 먼저 사용한 뒤 다른 명시적 non-empty provider ID를 가진 schema-compatible candidate 허용

untagged tool에는 provider-aware fallback을 추론하지 않습니다. primary tool에 명시적 `provider`가 없으면 provider fallback route도 compile하지 않습니다.

fallback candidate는 각자의 endpoint/tool fingerprint, argument, selected field, evidence contract, planning explanation을 가진 일반 `ToolCall` 값입니다. runtime은 plan compile 이후 새로운 route를 만들어내지 않습니다.

## Fallback에서도 field requirement는 고정

fallback은 SchemaRouter가 데이터를 얻는 **위치**를 바꾸지만 질문이 요구하는 데이터 **자체**는 바꾸지 않습니다.
primary call과 허용된 모든 fallback은 동일한 semantic need를 기준으로 각각 독립 compile됩니다. query에 elastic modulus가 필요하면 compatible elastic-modulus field를 노출할 수 없는 fallback은 제외됩니다.

endpoint가 `ServerProjectionSpec`을 선언하면 planned field도 upstream에 전달됩니다. 따라서 transport가 다르다는 이유만으로 fallback이 full record를 가져오지 않습니다. raw schema validation 이후에도 최종 local projection이 적용됩니다.

See [Field-first execution](../concepts/field-first-execution.md).

## Access path별 서로 다른 field 이름

access path마다 약간 다른 schema를 노출할 수 있습니다. stable canonical local field name을 유지하고 provider-specific wire name을 명시적으로 매핑합니다:

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    aliases=["탄성계수", "elastic modulus", "youngs modulus"],
    path=["_provider_b_elasticity"],
    result_path=["elastic_modulus"],
)

ServerProjectionSpec(
    parameter="response_fields",
    field_map={
        "elastic_modulus": "_provider_b_elasticity",
    },
)
```

planner는 canonical `elastic_modulus` field를 기준으로 판단합니다. adapter는 `_provider_b_elasticity`를 upstream으로 보내며 runtime projection은 provider-specific `path`를 읽고 result가 SchemaRouter를 벗어나기 전에 canonical `result_path`에 값을 기록합니다.

fallback planner는 candidate마다 field를 독립적으로 project합니다. primary가 특정 answer field와 match했다면 alternative가 compatible field/alias surface를 노출할 때만 fallback을 허용합니다. SchemaRouter가 compatibility를 입증할 수 없으면 route를 조용히 대체하지 않습니다.

이는 보수적인 동작입니다. provider-specific semantic mapping은 model output에서 추론하는 대신 local adapter 또는 application이 추가할 수 있습니다.

## Runtime fallback 발생 조건

SchemaRouter는 선택한 access path에 먼저 일반 retry policy를 적용합니다. invoker가 `InvocationUnavailableError`를 발생시킨 경우에만 다음 precompiled path로 이동합니다.

built-in remote adapter는 connection/timeout failure, HTTP 429, transient 5xx 같은 bounded transport failure를 unavailable로 분류합니다.

automatic fallback은 다음 경우 발생하지 **않습니다**:

- schema/input/output validation failures;
- policy or approval failures;
- stale fingerprints or stale bindings;
- deterministic/non-retryable invocation errors;
- normal 4xx request/auth/not-found responses;
- mutating or unclassified operations.

automatic fallback chain의 모든 candidate는 명시적으로 `read_only=True`여야 하며 primary invocation 전에 전체 chain을 preflight합니다.

## Passive cooldown과 active health recovery

timeout, connection failure, HTTP 429, transient 5xx를 반환한 route는 일반 retry policy를 모두 소진하면 일시적으로 unavailable로 표시됩니다. known-unavailable path는 이후 planner candidate surface에서 제외되므로 router는 매 query마다 동일한 network failure를 기다리는 대신 healthy alternative를 primary path로 선택할 수 있습니다.

이 상태는 **영구적이지 않습니다**. 모든 unavailable mark에는 유한 cooldown이 있으며 cooldown이 만료되면 route는 자동으로 다시 eligible 상태가 됩니다.

application은 trusted health probe를 사용해 route를 더 일찍 다시 열 수도 있습니다:

```python
async def mp_optimade_health() -> bool:
    # Use a cheap, trusted health/version check owned by the application.
    return await check_mp_optimade_health()

router.register_health_probe(
    "mp_optimade",
    "search_structures",
    mp_optimade_health,
)

await router.start_health_monitor(
    interval_seconds=30,
    probe_timeout_seconds=5,
)
```

probe가 성공하면 cooldown을 즉시 해제합니다. 실패한 probe는 bounded cooldown만 연장하며 route를 영구 blacklist하지 않습니다.

health monitor에는 엄격한 boundary가 있습니다:

- 명시적으로 등록된 trusted local callback만 실행됩니다.
- probe는 `read_only=True` access path에만 연결할 수 있습니다.
- SchemaRouter는 remote metadata에서 health request를 임의 생성하지 않습니다.
- 임의 data query를 probe로 조용히 변환하지 않습니다.
- model output은 route를 healthy/unhealthy로 표시할 수 없습니다.
- health failure는 availability에만 영향을 주며 schema/policy authority에는 영향을 주지 않습니다.

이미 external service health information을 가진 application은 background monitor를 시작하는 대신 `mark_access_unavailable(...)`과 `mark_access_available(...)`을 직접 호출할 수 있습니다.

## 같은 provider 우선, 이후 다른 provider

plan은 다음과 같이 구성될 수 있습니다:

```text
Materials Project / native API
  -> unavailable
Materials Project / OPTIMADE
  -> unavailable
Materials Project / Python client
  -> unavailable
OQMD / API
  -> success
```

이는 autonomous replanning이 아닙니다. alternative는 planning 단계에서 이미 local schema와 evidence로 제한되어 있습니다.

## Observability

typed event stream은 transition을 기록합니다:

```text
tool.start      mp_api.search
tool.error      InvocationUnavailableError
tool.fallback   -> mp_optimade.search   scope=same_provider
tool.start      mp_optimade.search
...
tool.fallback   -> oqmd_api.search      scope=cross_provider
```

`tool.fallback`에는 from/to tool과 endpoint, provider, access mode, transition이 동일 provider 내부에서 이루어졌는지가 포함됩니다.

최종 `ToolResult.tool`과 `ToolResult.endpoint`는 실제 성공한 route를 나타냅니다.

## Budget

fallback route는 primary route와 동일한 run budget을 사용합니다. 실제 fallback invocation은 각각 추가 logical tool call로 계산되며 attempt/cost unit도 정상적으로 차감됩니다.

따라서 fallback이 unbounded availability loop가 되는 것을 방지합니다.


## 모든 access path가 중단된 경우

일시적 unavailable 상태는 영구 blacklist가 아닙니다.

모든 eligible access path가 cooldown window 안에 있다면 planning은 known-failing network call을 반복하는 대신 해당 시점에 route가 없다고 정상적으로 반환할 수 있습니다. recovery는 다음 두 bounded mechanism 중 하나로 이루어집니다:

1. **Passive re-entry** — 모든 unavailable mark에는 유한 cooldown이 있습니다. 만료되면 access path는 자동으로 다시 planning 대상이 됩니다.
2. **Active background recovery** — trusted read-only health probe는 cooldown 만료 전에 복구된 path를 다시 열 수 있습니다.

예제:

```python
router.register_health_probe(
    "mp_optimade",
    "search_structures",
    mp_optimade_health,
)

await router.start_health_monitor(
    interval_seconds=30,
    probe_timeout_seconds=5,
    max_concurrency=4,
)
```

background monitor는 즉시 실행된 뒤 설정 interval마다 반복됩니다. probe 성공은 access-path cooldown을 해제해 다음 planning turn에서 해당 path를 다시 선택할 수 있게 합니다. probe 실패는 bounded cooldown만 연장하며 schema fingerprint, policy authority, provider field semantic은 변경하지 않습니다.

SchemaRouter는 임의의 health traffic을 **생성하지 않습니다**. generic REST/OpenAPI service에 보편적으로 안전한 health endpoint는 없으므로 probe는 명시적인 trusted local callback으로 유지됩니다. provider가 문서화된 저비용 read-only status/info endpoint를 제공한다면 application은 일반 data query 대신 해당 endpoint를 probe에 사용해야 합니다.

즉 all-down은 일시적인 availability state이지 복구 불가능한 terminal state가 아닙니다.


## Availability와 executability는 다릅니다

SchemaRouter는 다음 세 질문을 분리합니다:

1. **Schema/policy validity** — 이 호출이 현재 contract 기준으로 여전히 authorize/compile되어 있는가?
2. **Access health** — remote/local access path가 현재 bounded unavailable cooldown 밖에 있는가?
3. **Binding readiness** — trusted invoker가 현재 동일 tool fingerprint에 bind되어 있는가?

read-only fallback은 실행 전에 세 축 모두에서 valid해야 합니다.

현재 unbound, stale-bound 상태이거나 local policy에서 더 이상 valid하지 않은 optional fallback route는 primary invocation 전에 제거됩니다. 이들은 그 외에는 valid한 primary를 차단하지 않습니다. mutating fallback은 다릅니다. structural fallback contract를 위반하므로 전체 automatic fallback chain을 invalid하게 만듭니다.

planned primary가 schema/policy-valid하지만 현재 unbound라면 SchemaRouter는 다음 precompiled/bound/read-only alternative로 바로 이동할 수 있습니다. typed event에는 다음처럼 기록됩니다:

```text
tool.fallback  reason=binding_unavailable
```

primary의 schema drift와 policy violation은 계속 fail-closed되며 availability fallback으로 변환되지 않습니다.

Live inspection exposes both health and binding readiness:

```python
snapshot = router.inspect()
print(snapshot.execution.binding_states)
# {"mp_api": "ready", "mp_optimade": "unbound"}
# other possible states: "stale", "orphaned"

print(snapshot.execution.unavailable_access_paths)
# ["mp_api.search"]  # only when a bounded health cooldown is active
```

이를 통해 healthy-but-unbound route를 network outage와 혼동하지 않습니다.


`orphaned` binding은 해당 registry tool이 제거된 뒤에도 trusted invoker object가 local에 남아 있음을 뜻합니다. registry validation이 먼저 수행되므로 실행할 수 없지만 이 상태를 노출하면 healthy bound tool로 잘못 보이는 대신 cleanup/misconfiguration을 확인할 수 있습니다.


## Fallback 전에 executable route 우선

fallback은 planning 이후 나타나는 failure를 위한 runtime safety net입니다. live execution은 이미 local unbound로 알려진 route를 선택해서는 안 됩니다.

따라서 SchemaRouter의 execution-facing API는 다음 두 조건을 함께 사용해 planning합니다:

```text
access-health eligible
AND
current trusted binding ready
```

healthy하지만 unbound인 route는 schema-only `router.plan()`에는 나타날 수 있지만 `router.plan_executable()`과 일반 `invoke/stream` planning에서는 제외됩니다. plan compile 이후 binding state가 바뀌면 executor-level binding-aware fallback이 두 번째 방어선으로 남습니다.

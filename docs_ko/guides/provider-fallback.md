# Provider-aware access fallback

하나의 정보 provider가 동일한 underlying dataset을 여러 access path로 제공할 수 있습니다.

예를 들어 materials database는 다음을 함께 제공할 수 있습니다.

- native REST/OpenAPI API
- OPTIMADE endpoint
- Python client 또는 local wrapper

이 경로들은 authentication, availability, query parameter, response field, rate limit, deployment dependency가 서로 다를 수 있습니다. SchemaRouter는 이들을 동일한 logical `provider`를 공유할 수 있는 별도의 `ToolSpec` contract로 모델링합니다.

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

`provider`는 **누가 정보를 소유하거나 제공하는지**를 나타냅니다.  
`access_mode`는 **이 특정 contract가 어떤 방식으로 정보에 접근하는지**를 나타냅니다.

두 값 모두 fingerprinted tool contract의 일부입니다.

URL 및 Python registration API도 동일한 identity를 받습니다.

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

## Bounded fallback 컴파일

Fallback은 opt-in이며 기본적으로 비활성화됩니다.

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

Scope는 다음과 같습니다.

- `disabled`: automatic fallback 없음
- `same_provider`: 동일한 explicit non-empty provider ID를 가진 precompiled alternative만 허용
- `cross_provider`: same-provider alternative를 먼저 사용하고, 이후 다른 explicit non-empty provider ID를 가진 schema-compatible candidate를 허용

Provider-aware fallback은 tag가 없는 tool에 대해 추론되지 않습니다. Primary tool에 explicit `provider`가 없으면 provider fallback route도 컴파일하지 않습니다.

Fallback candidate는 각자의 endpoint/tool fingerprint, argument, selected field, evidence contract, planning explanation을 가진 일반 `ToolCall` 값입니다. Runtime은 plan이 컴파일된 이후 새로운 route를 발명하지 않습니다.

## Fallback에서도 field need는 고정

Fallback은 SchemaRouter가 데이터를 얻는 **위치**를 바꾸는 것이지, 질문에 필요한 **데이터의 의미**를 바꾸는 것이 아닙니다. Primary call과 허용된 모든 fallback은 동일한 semantic need에 대해 독립적으로 컴파일됩니다. 질문이 elastic modulus를 필요로 한다면 호환되는 elastic-modulus field를 제공할 수 없는 fallback은 제외됩니다.

Endpoint가 `ServerProjectionSpec`을 선언하면 planned field도 upstream으로 전달되므로 transport가 달라졌다는 이유만으로 fallback이 전체 record를 가져오지 않습니다. Raw schema validation 뒤에는 final local projection도 계속 적용됩니다.

[Field-first execution](../concepts/field-first-execution.md)을 참고하십시오.

## Access path마다 field 이름이 다른 경우

Access path는 종종 조금씩 다른 schema를 노출합니다. 안정적인 canonical local field name을 유지하고 provider-specific wire name을 명시적으로 매핑하십시오.

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

Planner는 canonical `elastic_modulus` field를 기준으로 추론합니다. Adapter는 upstream에 `_provider_b_elasticity`를 전송합니다. Runtime projection은 provider-specific `path`에서 값을 읽어 SchemaRouter 밖으로 결과가 나가기 전에 canonical `result_path`에 기록합니다.

Fallback planner는 각 candidate의 field를 독립적으로 project합니다. Primary가 특정 answer field와 매칭됐다면 alternative가 호환되는 field/alias surface를 노출할 때만 fallback으로 허용합니다. SchemaRouter가 compatibility를 증명할 수 없으면 route를 조용히 대체하지 않습니다.

이는 보수적인 설계입니다. Provider-specific semantic mapping은 model output에서 추론하는 대신 local adapter 또는 application이 추가할 수 있습니다.

## Runtime fallback이 발생하는 시점

SchemaRouter는 먼저 선택된 access path에 일반 retry policy를 적용합니다. Invoker가 `InvocationUnavailableError`를 발생시킨 경우에만 다음 precompiled path로 이동합니다.

Built-in remote adapter는 connection/time-out failure, HTTP 429, transient 5xx response와 같은 제한된 transport failure를 unavailable로 분류합니다.

다음 상황에서는 automatic fallback이 발생하지 않습니다.

- schema/input/output validation failure
- policy 또는 approval failure
- stale fingerprint 또는 stale binding
- deterministic/non-retryable invocation error
- 일반적인 4xx request/auth/not-found response
- mutating 또는 분류되지 않은 operation

Automatic fallback chain의 모든 candidate는 명시적으로 `read_only=True`여야 하며 primary가 호출되기 전에 전체 chain을 preflight합니다.

## Passive cooldown과 active health recovery

Timeout, connection 실패, HTTP 429 또는 transient 5xx response를 반환하는 route는 일반 retry policy가 소진된 뒤 일시적으로 unavailable로 표시됩니다. Known-unavailable path는 이후 planner candidate surface에서 제외되므로 router는 질문마다 동일한 실패 network wait를 반복하는 대신 healthy alternative를 primary path로 선택할 수 있습니다.

이 상태는 **영구적이지 않습니다**. 모든 unavailable mark에는 유한한 cooldown이 있습니다. Cooldown이 만료되면 route는 자동으로 다시 eligible 상태가 됩니다.

Application은 trusted health probe를 사용해 더 일찍 route를 다시 열 수도 있습니다.

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

성공한 probe는 cooldown을 즉시 해제합니다. 실패한 probe는 bounded cooldown만 연장하며 route를 영구 blacklist하지 않습니다.

Health monitor에는 다음과 같은 엄격한 경계가 있습니다.

- 명시적으로 등록된 trusted local callback만 실행
- probe는 `read_only=True` access path에만 연결 가능
- SchemaRouter는 remote metadata에서 health request를 발명하지 않음
- 임의의 data query를 조용히 probe로 변환하지 않음
- model output은 route를 healthy/unhealthy로 표시할 수 없음
- health failure는 availability에만 영향을 주며 schema/policy authority에는 영향을 주지 않음

이미 외부 service health 정보를 보유한 application은 background monitor를 시작하는 대신 `mark_access_unavailable(...)` 및 `mark_access_available(...)`을 직접 호출할 수 있습니다.

## 같은 provider를 먼저, 그다음 다른 provider

Plan은 다음과 같이 encode될 수 있습니다.

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

이는 autonomous replanning이 아닙니다. Alternative는 planning 시점에 이미 local schema와 evidence로 범위가 제한돼 있습니다.

## Observability

Typed event stream은 전환을 기록합니다.

```text
tool.start      mp_api.search
tool.error      InvocationUnavailableError
tool.fallback   -> mp_optimade.search   scope=same_provider
tool.start      mp_optimade.search
...
tool.fallback   -> oqmd_api.search      scope=cross_provider
```

`tool.fallback`에는 from/to tool과 endpoint, provider, access mode, 전환이 같은 provider 내부였는지 여부가 포함됩니다.

최종 `ToolResult.tool`과 `ToolResult.endpoint`는 실제로 성공한 route를 식별합니다.

## Budgets

Fallback route는 primary route와 동일한 run budget을 소비합니다. 실제 fallback invocation 하나마다 logical tool call 하나로 계산되며 attempt/cost unit도 정상적으로 청구됩니다.

따라서 fallback이 무제한 availability loop가 되는 것을 방지합니다.

## 모든 access path가 down이면?

Temporary unavailability는 영구 blacklist가 아닙니다.

Eligible access path가 모두 cooldown window 안에 있다면 planning은 known-failing network call을 반복해서 기다리는 대신 그 순간에는 합법적으로 no route를 반환할 수 있습니다. Recovery는 두 가지 bounded mechanism을 통해 이뤄집니다.

1. **Passive re-entry** — 모든 unavailable mark에는 유한한 cooldown이 있습니다. 만료되면 access path가 자동으로 planning 대상이 됩니다.
2. **Active background recovery** — trusted read-only health probe가 cooldown 만료 전에 recovered path를 다시 열 수 있습니다.

예:

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

Background monitor는 즉시 한 번 실행된 뒤 설정된 interval마다 반복됩니다. Probe 성공은 access-path cooldown을 해제하므로 다음 planning turn에서 해당 path를 선택할 수 있습니다. Probe 실패는 bounded cooldown만 연장하며 schema fingerprint, policy authority, provider field semantics를 변경하지 않습니다.

SchemaRouter는 임의의 health traffic을 합성하지 않습니다. Generic REST/OpenAPI service에는 보편적으로 안전한 health endpoint가 없으므로 probe는 explicit trusted local callback으로 유지됩니다. Provider가 문서화된 저비용 read-only status/info endpoint를 제공한다면 application은 일반 data query 대신 해당 endpoint를 probe에 사용해야 합니다.

즉 all-down 상태는 temporary availability state이며 absorbing terminal state가 아닙니다.

## Availability와 executability는 다름

SchemaRouter는 세 가지 질문을 구분합니다.

1. **Schema/policy validity** — 이 call이 여전히 authorized 상태이며 현재 contract를 기준으로 컴파일돼 있는가?
2. **Access health** — remote/local access path가 현재 bounded unavailable cooldown 밖에 있는가?
3. **Binding readiness** — trusted invoker가 현재 동일한 tool fingerprint에 bind돼 있는가?

Read-only fallback은 세 축 모두에서 valid해야 실행할 수 있습니다.

현재 unbound, stale-bound 또는 local policy 아래에서 더 이상 valid하지 않은 optional fallback route는 primary invocation 전에 제거됩니다. 이들은 유효한 primary를 막지 않습니다. 반면 mutating fallback은 structural fallback contract를 위반하므로 automatic fallback chain 전체를 invalid하게 만듭니다.

Planned primary가 schema/policy-valid이지만 현재 unbound라면 SchemaRouter는 다음 precompiled, bound, read-only alternative로 바로 이동할 수 있습니다. Typed event는 이를 다음과 같이 기록합니다.

```text
tool.fallback  reason=binding_unavailable
```

Primary의 schema drift와 policy violation은 계속 fail-closed하며 availability fallback으로 변환되지 않습니다.

Live inspection은 health와 binding readiness를 모두 노출합니다.

```python
snapshot = router.inspect()
print(snapshot.execution.binding_states)
# {"mp_api": "ready", "mp_optimade": "unbound"}
# other possible states: "stale", "orphaned"

print(snapshot.execution.unavailable_access_paths)
# ["mp_api.search"]  # only when a bounded health cooldown is active
```

따라서 healthy-but-unbound route를 network outage로 혼동하지 않습니다.

`orphaned` binding은 해당 registry tool이 제거된 뒤에도 trusted invoker object가 local에 남아 있다는 뜻입니다. Registry validation이 먼저 실행되므로 이 binding은 실행될 수 없지만, 상태를 노출함으로써 cleanup/misconfiguration을 healthy bound tool처럼 보이지 않게 합니다.

## Fallback 전에 executable route 우선

Fallback은 planning 이후 나타나는 failure를 위한 runtime safety net입니다. Live execution은 이미 locally unbound임이 알려진 route를 선택해서는 안 됩니다.

따라서 SchemaRouter의 execution-facing API는 다음 두 조건을 모두 만족하는 route만 planning합니다.

```text
access-health eligible
AND
current trusted binding ready
```

Healthy하지만 unbound인 route는 schema-only `router.plan()`에는 나타날 수 있지만 `router.plan_executable()`과 일반 `invoke/stream` planning에서는 제외됩니다. Plan이 컴파일된 뒤 binding state가 변경되면 executor-level binding-aware fallback이 두 번째 방어선으로 남습니다.

# Provider-aware access fallback

One information provider can expose the same underlying dataset through multiple access paths.

A materials database may provide, for example:

- a native REST/OpenAPI API;
- an OPTIMADE endpoint;
- a Python client or local wrapper.

Those paths can differ in authentication, availability, query parameters, response fields, rate
limits, and deployment dependencies. SchemaRouter models them as separate `ToolSpec` contracts
that can share one logical `provider`.

## Provider and access identity

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

`provider` answers **who owns/provides the information**.
`access_mode` answers **how this particular contract reaches it**.

Both values are part of the fingerprinted tool contract.

URL and Python registration APIs accept the same identity:

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

## Compile bounded fallbacks

Fallback is opt-in and disabled by default.

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

The scopes are:

- `disabled`: no automatic fallback;
- `same_provider`: only precompiled alternatives with the same non-empty provider ID;
- `cross_provider`: same-provider alternatives first, then schema-compatible candidates from
  other providers.

Fallback candidates are normal `ToolCall` values with their own endpoint/tool fingerprints,
arguments, selected fields, evidence contract, and planning explanation. Runtime does not invent a
new route after the plan was compiled.

## Different field names across access paths

Access paths often expose slightly different schemas. Use `FieldSpec.aliases` to declare semantic
equivalence where it is locally known:

```python
FieldSpec(
    name="_mp_band_gap",
    aliases=["band gap", "band_gap"],
    unit="eV",
)
```

The fallback planner independently projects fields for every candidate. When the primary matched a
specific answer field, a fallback is accepted only when the alternative exposes a compatible
field name/alias surface. If SchemaRouter cannot prove that compatibility, it does not silently
substitute the route.

This is intentionally conservative. Provider-specific semantic mappings can be added by the local
adapter or application rather than inferred from model output.

## When runtime fallback occurs

SchemaRouter first applies the normal retry policy to the selected access path. It moves to the next
precompiled path only when the invoker raises `InvocationUnavailableError`.

Built-in remote adapters classify bounded transport failures such as connection/time-out failures,
HTTP 429, and transient 5xx responses as unavailable.

Automatic fallback does **not** occur for:

- schema/input/output validation failures;
- policy or approval failures;
- stale fingerprints or stale bindings;
- deterministic/non-retryable invocation errors;
- normal 4xx request/auth/not-found responses;
- mutating or unclassified operations.

All candidates in an automatic fallback chain must be explicitly `read_only=True`, and the entire
chain is preflighted before the primary is invoked.

## Same provider first, then another provider

A plan may therefore encode:

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

This is not autonomous replanning. The alternatives were already bounded by local schemas and
evidence during planning.

## Observability

Typed event streams record the transition:

```text
tool.start      mp_api.search
tool.error      InvocationUnavailableError
tool.fallback   -> mp_optimade.search   scope=same_provider
tool.start      mp_optimade.search
...
tool.fallback   -> oqmd_api.search      scope=cross_provider
```

`tool.fallback` includes the from/to tool and endpoint, provider, access mode, and whether the
transition stayed within the same provider.

The final `ToolResult.tool` and `ToolResult.endpoint` identify the route that actually succeeded.

## Budgets

Fallback routes consume the same run budget as the primary route. Every actual fallback invocation
counts as another logical tool call and its attempts/cost units are charged normally.

This prevents fallback from becoming an unbounded availability loop.

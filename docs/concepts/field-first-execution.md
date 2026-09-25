# Field-first execution

SchemaRouter is designed around a **field-first, route-second** principle.

The goal is not merely to choose a tool. The goal is to identify the smallest declared data surface
that can answer the user's question, then choose a trusted access path that can provide that surface.

```text
user query
  -> semantic data need
  -> required logical fields
  -> providers/access paths that can supply those fields
  -> availability + policy + evidence
  -> server-side field selection when supported
  -> raw schema validation
  -> final local projection
  -> minimal ToolResult context
```

## Why field-first matters

If a user asks for one material property such as elastic modulus, fetching a complete material
record can create avoidable cost:

- more upstream response bytes and latency;
- more JSON parsing and validation work;
- more irrelevant values in downstream LLM context;
- more prompt tokens;
- a higher chance that unrelated properties distract answer generation.

SchemaRouter therefore treats response fields as part of the execution plan rather than an
afterthought.

## Logical fields before provider selection

Different providers and access modes can expose the same concept under different names:

```text
elastic modulus
  -> provider A / REST       -> elastic_modulus
  -> provider B / OPTIMADE   -> _b_elasticity
  -> provider C / Python     -> youngs_modulus
```

Local `FieldSpec` contracts declare known semantic equivalence. Prefer one canonical local
`FieldSpec.name` for the concept. Keep provider-specific request selector names in
`ServerProjectionSpec.field_map`, provider response locations in `FieldSpec.path`, and use
`FieldSpec.result_path` when the final projected result should be written to a different canonical
location. `aliases` help the planner recognize user phrasing and legacy/provider terminology.

For example, all three access paths can expose the local field `elastic_modulus` while mapping it
to `elastic_modulus`, `_b_elasticity`, or `youngs_modulus` on the wire. A provider-specific
source path can still be projected into `result_path=["elastic_modulus"]`, so the planner and final
`ToolResult` stay provider-neutral.

The model does not get to invent field mappings.

## Two layers of projection

SchemaRouter minimizes data at two different boundaries.

### 1. Server-side projection

When an endpoint has an explicit trusted `ServerProjectionSpec`, planned fields are pushed into
the upstream request:

```python
EndpointSpec(
    name="search",
    # ...
    server_projection=ServerProjectionSpec(
        parameter="fields",
        field_map={
            "elastic_modulus": "elasticity.bulk_modulus",
        },
    ),
)
```

A call selecting only:

```text
material_id
elastic_modulus
```

can therefore become:

```text
GET /materials?fields=material_id,elasticity.bulk_modulus
```

SchemaRouter never guesses that a generic OpenAPI parameter means field projection. The contract
must be declared locally or by a trusted adapter. OPTIMADE's `response_fields` is a built-in
example.

### 2. Final local projection

Even when an upstream service ignores or cannot perform server-side projection, SchemaRouter
validates the raw response and then keeps only the planned logical fields before producing the
`ToolResult`.

So the downstream answer-generation context stays narrow even when the provider returns a broader
payload.

## Availability changes the route, not the data need

The requested field surface remains stable while access paths can change:

```text
need: elastic modulus

provider A / REST
  healthy -> eligible for planning

provider B / OPTIMADE
  known unavailable -> excluded from the current planner candidate surface

provider C / API
  fallback -> use only if it can provide elastic modulus
```

Fallback does not broaden the requested fields merely because the preferred route failed.
A newly observed outage is handled by the precompiled fallback chain; once that route enters the
bounded cooldown, later plans exclude it until the cooldown expires or a trusted health signal
reopens it.

See [Provider-aware fallback](../guides/provider-fallback.md).

## Passive and active availability

Transport failures such as timeouts, connection failures, HTTP 429, or transient 5xx responses can
place an access path into a bounded cooldown. Cooldown always expires, so a path is never permanently
blacklisted by one failure.

For faster recovery, applications can register trusted read-only health probes. A background health
monitor can reopen a path immediately after a probe succeeds.

The monitor never invents a probe and never turns arbitrary data calls into health checks.

## Recall-first safety boundary

Field minimization is aggressive only when the query-to-field match is clear.

If SchemaRouter cannot confidently identify the answer field, the default planner preserves declared
fields rather than pretending to know which one is sufficient. This protects answer recall.

So the rule is:

```text
clear semantic match -> minimize
ambiguous semantic need -> preserve recall
```

Applications that need stronger domain-specific minimization should improve local aliases/schemas or
use a bounded analyzer rather than weakening validation.

# Design principles

SchemaRouter is built around a narrow idea: **the user's data need is primary; tools, providers,
and transports are replaceable implementation paths beneath that need.**

This page collects the principles that should guide new runtime features, adapters, and integrations.

## 1. Resolve the information need before the route

Planning starts from the smallest declared semantic field surface that can answer the query.

```text
user query
  -> semantic data need
  -> logical fields
  -> eligible providers/access paths
  -> validated execution
```

The planner should not start by asking "which API should I call?" and then accept whatever that API
returns. Provider selection comes after the required data surface is identified.

## 2. Provider and access mode are different identities

One organization can expose the same underlying information through several access paths.

```text
Materials Project
  -> native REST / OpenAPI
  -> OPTIMADE
  -> Python client
```

SchemaRouter therefore separates:

- `provider`: who owns or supplies the information;
- `access_mode`: how this contract reaches it;
- tool/endpoint: the concrete executable schema boundary.

Equivalent access paths may be fallback alternatives without being treated as different semantic
answers.

## 3. Fields are contracts, not just response keys

A logical field can carry more than a name:

- a canonical `semantic_id`;
- provider-specific source and result paths;
- aliases;
- JSON datatype/shape;
- optional unit metadata and explicit normalization;
- exact qualifiers such as temperature, pressure, phase, orientation, or measurement method;
- provenance/license/source-type metadata where declared.

Provider wire names never become semantic equivalence merely because a model says so. Mappings are
trusted local contracts.

## 4. Units are optional because semantics differ

`FieldSpec.unit` is optional for every capability source. Unitless does not mean "web text only."

Strings, identifiers, categories, booleans, structured metadata, dates represented by a declared
schema, and dimensionless numeric values may all legitimately have `unit=None`. A scientific
quantity may declare a source unit and, when needed, an explicit normalization contract.

The source type does not decide whether a unit exists. The field semantics do.

## 5. One query may require several sources

A query can require a union of fields that no single endpoint provides.

```text
need: band_gap + paper abstract

band_gap
  -> Materials Project / OpenAPI
  -> Materials Project / OPTIMADE

paper abstract
  -> arXiv / API
```

When the application explicitly permits multiple calls with `PlanRequest.max_calls > 1`,
SchemaRouter prefers complementary semantic-field coverage over spending limited call slots on
equivalent routes for an already-covered field.

The bound is still explicit. SchemaRouter never silently raises `max_calls`.

## 6. Health belongs to an access path, not to a semantic field

A field itself is not "alive" or "dead." An access path that can supply it may be healthy,
unavailable, unbound, or stale.

Effective field availability is derived from the currently trusted routes capable of satisfying that
field contract.

```text
elastic_modulus
  -> provider A / OpenAPI   unavailable
  -> provider A / OPTIMADE  healthy
  -> provider B / API       healthy
```

Temporary failures use finite cooldowns and optional trusted read-only health probes. One failure
must not create a permanent blacklist.

## 7. Availability may change the route, never the semantic requirement

Fallback may change provider or access mode, but it must preserve the required field semantics.

For scientific values this includes compatible datatype, unit/canonical-unit contracts, and exact
qualifiers when those qualifiers are part of the need. If compatibility cannot be proven locally,
the fallback is rejected.

## 8. Minimize data twice

When a trusted server-side projection contract exists, planned fields are requested upstream.
After raw-response validation, local projection narrows the final `ToolResult` again.

This reduces provider payload, parsing work, and downstream LLM context without weakening raw schema
validation.

## 9. Models may assist selection, not create authority

Optional hosted or local decision backends operate over finite locally registered candidates. They
cannot invent tools, schemas, credentials, health state, mutation authority, or new execution loops.

SchemaRouter is therefore a bounded planning/execution layer, not another agent framework.

## 10. Fail closed where equivalence cannot be proven

Schema drift, unsupported schema semantics, ambiguous aliases, incompatible scientific contracts,
stale bindings, and policy failures should remain visible failures rather than hidden coercions.

Recall can be preserved when field intent is ambiguous, but execution authority is never inferred.

## 11. Observability should expose structure, not hidden reasoning

Inspection, plan explanations, traces, and dashboards should expose the locally observable facts
that affected routing:

- selected tool/endpoint/provider/access mode;
- selected fields;
- deterministic score components;
- health/binding state;
- fallback transitions;
- schema fingerprints and field contracts.

They should not expose or depend on private model chain-of-thought.

## Design test

A new feature belongs in SchemaRouter when it strengthens this boundary:

```text
natural-language request
  -> bounded semantic field plan
  -> trusted route selection
  -> validated execution
  -> minimal typed result
```

If the feature instead owns conversation memory, autonomous tool loops, graph orchestration, or
general agent strategy, it belongs above SchemaRouter.

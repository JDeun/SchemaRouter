# Architecture and adversarial design review

## Decision

SchemaRouter is a **schema-aware planning and execution layer** for LLM tool ecosystems. It is not a general-purpose agent framework, model router, or MCP replacement.

The core is designed around one principle:

> model output and remote schemas may describe capabilities, but only trusted local code grants execution authority.

## Core flow

```text
request
  -> QueryAnalyzer
  -> schema-constrained intent
  -> candidate tool / endpoint
  -> parameter + field plan
  -> schema fingerprint
  -> execution policy
  -> JSON Schema input validation
  -> trusted invoker
  -> JSON Schema output validation
  -> field projection
  -> ToolResult
```

## Module boundaries

```text
schemarouter.models        typed tool / endpoint / plan contracts
schemarouter.registry      versioned namespaced catalog
schemarouter.planner       deterministic candidate scoring + recall-first projection
schemarouter.analyzers     optional model-assisted intent extraction
schemarouter.validation    JSON Schema runtime validation
schemarouter.policy        trusted local side-effect authority
schemarouter.runs          run configuration, retry policy, typed lifecycle events
schemarouter.executor      plan, binding, schema and policy enforcement
schemarouter.adapters      adapter contracts + OpenAPI/MCP/OPTIMADE/Python implementations
schemarouter.ingestion     AdapterRegistry dispatch, safe source loading, registry binding
schemarouter.proposals     evidence-grounded HTML documentation proposals
schemarouter.integrations  optional ecosystem bridges such as LangChain
schemarouter.runtime       high-level invoke/batch/stream facade
```

## Adversarial findings and responses

### 1. Tool routing alone is commoditized

A semantic `query -> tool` router is not enough differentiation. SchemaRouter makes tool,
endpoint, parameter, output field, evidence requirements, schema identity, execution authority,
and result projection explicit contracts.

### 2. The research harness flattened endpoint identity

The research artifact conventionally used one search endpoint per tool. Production OpenAPI and MCP
servers expose many operations. `ToolSpec` therefore owns multiple first-class `EndpointSpec`
objects.

### 3. Aggressive field minimization harms recall

The research results showed that minimizing field count can remove answer-critical information.
The v0.1 planner keeps identifiers, keeps confidently matched fields, and falls back to the full
declared top-level field set when output intent is ambiguous.

### 4. Remote schemas drift independently

Every endpoint and tool has a canonical schema fingerprint. A plan compiled against an older
endpoint is rejected. A bound invoker tied to an older tool contract is also rejected after the
registry changes.

### 5. Model analysis is untrusted

`ModelQueryAnalyzer` returns a structured proposal, not an executable command. Unknown tools,
endpoints, parameters, fields, and extra JSON keys are rejected or removed. Explicit caller
arguments override model-produced values.

Descriptions from remote schemas are passed to models only as untrusted data and cannot extend the
registry or execution authority.

### 6. Remote authorization metadata is untrusted

MCP annotations and OpenAPI descriptions never grant permissions. Sensitive runtime credentials
stay outside model-visible schemas.

For OpenAPI, `Authorization`, `Cookie`, `Host`, proxy authorization, connection framing, and
other sensitive runtime headers cannot be supplied through tool arguments.

### 7. Schema fetch credentials and API credentials are different trust domains

`schema_headers` are used only to fetch an OpenAPI document. `trusted_headers` are injected only
by the runtime invoker. OpenAPI document redirects are followed manually and only within the
original origin, preventing schema-fetch credentials from crossing origins.

### 8. OpenAPI documents can point at another host

A cross-origin `servers` entry is treated as descriptive, not executable authority. SchemaRouter
imports the schema but leaves it unbound until trusted local code supplies `base_url` or calls
`bind_openapi()`.

Runtime HTTP redirects are disabled and endpoint paths are constrained to the approved origin/base
path.

### 9. Declared parameter names are not enough

The executor validates the actual argument object against JSON Schema immediately before
invocation. Type, enum, range, required-property, pattern, and other supported constraints therefore
cannot be bypassed by manually constructing a `ToolCall`.

Raw structured tool output is validated before projection, so field projection cannot hide an
invalid response.

### 10. Side effects require local authority

The default `ExecutionPolicy` blocks known remote mutations and destructive operations. It also
blocks MCP operations whose side effects are not trusted locally because MCP annotations remain
untrusted.

Local application code may explicitly opt into:

- `allow_mutations=True`
- `allow_destructive=True`
- `allow_unclassified_remote=True`

A model or remote schema cannot set these flags.

### 11. Human-readable documentation is not an executable contract

`inspect_url()` creates a non-executable `SchemaProposal`. Every accepted endpoint, parameter,
and field must cite an exact quote found in the fetched document. Script/style content is removed
before model analysis.

`approve_proposal()` is a separate authority transition with grounding thresholds, explicit API
base URL, and mutation opt-in. Runtime execution policy remains an independent second gate.

### 12. Protocol diversity must not leak into the planner

v0.2 introduces `AdapterRegistry`. OpenAPI, OPTIMADE, MCP, and future structured protocols compile
into the same `ToolSpec` / `EndpointSpec` model. The planner does not branch on protocol type.

Call-aware invokers may receive the validated `ToolCall` when a protocol needs selected fields at
transport time. The executor still owns schema, policy, retry, and binding-drift enforcement.

## Core invariants

1. A plan cannot call an unregistered tool or endpoint.
2. A plan cannot pass undeclared parameters.
3. Required parameters are recomputed at execution; a forged plan cannot suppress them.
4. Arguments must satisfy the current endpoint input JSON Schema.
5. Requested projection fields must be declared by the current endpoint.
6. Raw tool output must satisfy the current endpoint output JSON Schema before projection.
7. A stale endpoint fingerprint cannot execute.
8. A stale invoker binding cannot execute after tool replacement.
9. Remote metadata cannot grant authorization.
10. Known remote mutations/destructive operations require local policy opt-in.
11. Unclassified remote MCP operations require local policy opt-in.
12. Schema-fetch credentials cannot cross an origin redirect.
13. Cross-origin OpenAPI server declarations require explicit local binding.
14. Runtime API secrets are not model-visible tool parameters.
15. Ambiguous output selection favors recall over aggressive pruning.
16. Automatic retries apply only to endpoints trusted as read-only unless local code opts in.
17. Run-event arguments and result payloads are redacted unless payload tracing is explicitly enabled.
18. Optional framework integrations call back through the same executor boundary rather than bypassing policy or validation.

## Intentionally deferred after v0.1 core

- authenticated/custom-transport MCP clients;
- trusted local classification for individual MCP tool side effects;
- OpenAPI external refs and richer `oneOf` / `allOf` / recursive-schema handling;
- non-object request-body ergonomics and richer nested field projection;
- per-call human approval, quotas, cost budgets, license/provenance policy extensions;
- compensation, transactions, and distributed execution;
- persistent/distributed registries;
- multi-page and client-rendered documentation crawling;
- callback exporters, OpenTelemetry integration, replay, and benchmark tooling;
- LangGraph-native integration adapters.

These are extension layers. They should not weaken the core fail-closed contracts above.

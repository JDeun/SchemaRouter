# Architecture and adversarial design review

## Decision

The framework direction passes with constraints. The viable product is a **schema-aware planning and execution layer**, not a general-purpose agent framework.

## Adversarial findings

### 1. "Tool routing" alone is already commoditized

A framework that only retrieves a relevant tool by semantic similarity has weak differentiation. SchemaRouter therefore treats the following as first-class contracts: tool, endpoint/operation, parameter, output field, evidence requirement, schema fingerprint, and execution result.

### 2. The paper harness flattened endpoint identity

The research artifact conventionally used `<tool>.search`. Real OpenAPI and MCP ecosystems have many operations per provider/server. v0.1 removes the 1:1 assumption: `ToolSpec` owns multiple `EndpointSpec` objects.

### 3. Aggressive field minimization can hurt downstream recall

The research results show that field-count parsimony is the wrong objective when it drops answer-critical fields. v0.1 therefore uses recall-preserving projection: identifiers are retained, explicit concept matches are projected, and ambiguous/no-match cases default to the endpoint's output schema instead of silently pruning it. Future planners may optimize token cost, but only under an explicit recall policy.

### 4. Remote schemas drift

MCP/OpenAPI providers can change independently from an agent workflow. Replaying a stale plan against a changed schema is unsafe and difficult to debug. Every endpoint has a stable canonical fingerprint. Plans store that fingerprint and the executor rejects stale plans (`SchemaDriftError`) unless a caller explicitly replans.

### 5. MCP names are not globally unique

MCP tool names are unique only within a server. The registry therefore supports namespaces and does not rely on a remote server display name as a globally unique identifier. Callers should use stable local server IDs as namespaces.

### 6. Tool annotations and remote metadata are untrusted input

Adapters parse schemas, but do not convert remote annotations into trusted authorization policy. Credentials, approvals, and privileged runtime arguments must be injected by trusted caller/runtime code, not selected by the model.

### 7. Framework scope can explode

The core does not own chat history, memory, vector stores, prompting, or agent graphs. Integrations should adapt SchemaRouter to those systems rather than absorb their responsibilities.

## v0.1 module boundaries

```text
schemarouter.models       typed schema and plan contracts
schemarouter.registry     versioned in-memory catalog and collision checks
schemarouter.planner      deterministic candidate scoring + field projection
schemarouter.executor     stale-plan validation + pluggable invocation
schemarouter.adapters     schema ingestion (MCP/OpenAPI)
```

## Invariants

1. A plan cannot call an unregistered tool or endpoint.
2. A plan cannot pass undeclared parameters.
3. A plan with missing required parameters is not executable.
4. A stale endpoint fingerprint is not executable.
5. Unknown/ambiguous output needs favor recall over aggressive pruning.
6. Adapter parsing never grants permissions.

## Deferred deliberately

- model/provider integrations
- embeddings/vector retrieval
- HTTP/MCP transports
- retries and compensation semantics
- distributed schema registry
- policy DSL
- telemetry backends

These are extension points after the core contracts survive real integration tests.


## Model-assisted query analysis

Model-assisted understanding is an optional analysis stage, not an authority boundary.

The model receives a structured registry catalog plus a response JSON schema. Its output is
validated, then projected onto the registry before planning. Unknown tools, endpoints, parameters,
and fields are discarded. Explicit caller arguments override model-generated values.

Async analyzers use `aplan()` / `arun()`; the existing synchronous `plan()` remains deterministic
and rejects an async analyzer with an explicit error instead of creating an implicit event loop.

Remote descriptions are included only as untrusted data. They cannot expand permissions, register
new executable schemas, or bypass executor validation.


## Unstructured documentation trust boundary

Human-readable documentation is never auto-promoted to an executable contract.

`inspect_url()` produces a `SchemaProposal`. Each proposed endpoint, parameter, and field must
carry an exact quote that can be found in the fetched document after normalization. Items without
grounded evidence are dropped. Script/style content is excluded before the model sees the page.

`approve_proposal()` is the explicit authority transition. It requires a caller-supplied API base
URL, a minimum grounding score, and a separate opt-in for mutating HTTP methods. Credentials are
kept outside both the proposal and URL. Only after these checks is a runtime invoker bound.

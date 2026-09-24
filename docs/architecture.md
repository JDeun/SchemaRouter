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
schemarouter.registry      versioned namespaced catalog + optional SQLite persistence
schemarouter.planner       exact-recall candidate indexing + deterministic scoring + recall-first projection
schemarouter.analyzers     optional model-assisted intent extraction
schemarouter.validation    JSON Schema runtime validation
schemarouter.policy        trusted local side-effect + approval authority
schemarouter.runs          run configuration, retry policy, budgets, typed lifecycle events
schemarouter.traces        validated append-only run-event persistence + non-executing replay
schemarouter.hooks         trusted snapshot-only before/after execution middleware
schemarouter.executor      plan, binding, schema, policy and hook enforcement
schemarouter.adapters      adapter contracts + OpenAPI/MCP/OPTIMADE/Python implementations
schemarouter.ingestion     AdapterRegistry dispatch, safe source loading, registry binding
schemarouter.proposals     evidence-grounded HTML documentation proposals
schemarouter.integrations  optional LangChain/LlamaIndex/Jev/OpenTelemetry integrations
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

### 3. Candidate indexing must not change planner recall

Large registries should not require scoring every endpoint on every request, but approximate
prefilters can silently remove valid tools. SchemaRouter therefore indexes every input that can
produce a positive deterministic score under the current scorer and still runs the unchanged
scoring function on the resulting candidates. The index is cached by registry version and can be
disabled for exhaustive parity checks.

### 4. Aggressive field minimization harms recall

The research results showed that minimizing field count can remove answer-critical information.
The planner keeps identifiers, keeps confidently matched fields, and falls back to the full
declared field set when output intent is ambiguous. `FieldSpec.path` can map a bounded logical
field ID onto a nested object path without exposing arbitrary JSONPath syntax to planning.

### 5. Remote schemas drift independently

Every endpoint and tool has a canonical schema fingerprint. A plan compiled against an older
endpoint is rejected. A bound invoker tied to an older tool contract is also rejected after the
registry changes.

### 6. Model analysis is untrusted

`ModelQueryAnalyzer` returns a structured proposal, not an executable command. Unknown tools,
endpoints, parameters, fields, and extra JSON keys are rejected or removed. Explicit caller
arguments override model-produced values.

Descriptions from remote schemas are passed to models only as untrusted data and cannot extend the
registry or execution authority.

### 7. Remote authorization metadata is untrusted

MCP annotations and OpenAPI descriptions never grant permissions. Sensitive runtime credentials
stay outside model-visible schemas.

For OpenAPI, `Authorization`, `Cookie`, `Host`, proxy authorization, connection framing, and
other sensitive runtime headers cannot be supplied through tool arguments.

### 8. Schema fetch credentials and API credentials are different trust domains

`schema_headers` are used only for OpenAPI schema retrieval. `trusted_headers` are injected only
by the runtime invoker. OpenAPI document redirects are followed manually and only within the
original origin, preventing schema-fetch credentials from crossing origins. Cross-document
`$ref` retrieval is disabled by default; when explicitly enabled, it reuses schema headers only for
same-origin referenced documents and remains bounded by redirect/depth/document/byte limits.

### 9. OpenAPI documents can point at another host

A cross-origin `servers` entry is treated as descriptive, not executable authority. SchemaRouter
imports the schema but leaves it unbound until trusted local code supplies `base_url` or calls
`bind_openapi()`.

Runtime HTTP redirects are disabled and endpoint paths are constrained to the approved origin/base
path.

### 10. Declared parameter names are not enough

The executor validates the actual argument object against JSON Schema immediately before
invocation. Type, enum, range, required-property, pattern, and other supported constraints therefore
cannot be bypassed by manually constructing a `ToolCall`.

Raw structured tool output is validated before projection, so field projection cannot hide an
invalid response.

### 11. Side effects require local authority

The default `ExecutionPolicy` blocks known remote mutations and destructive operations. It also
blocks MCP operations whose side effects are not trusted locally because MCP annotations remain
untrusted.

Local application code may explicitly opt into:

- `allow_mutations=True`
- `allow_destructive=True`
- `allow_unclassified_remote=True`

A model or remote schema cannot set these flags.

### 12. Human-readable documentation is not an executable contract

`inspect_url()` creates a non-executable `SchemaProposal`. Every accepted endpoint, parameter,
and field must cite an exact quote found in the fetched document. Script/style content is removed
before model analysis.

`approve_proposal()` is a separate authority transition with grounding thresholds, explicit API
base URL, and mutation opt-in. Runtime execution policy remains an independent second gate.

### 13. Protocol diversity must not leak into the planner

v0.2 introduces `AdapterRegistry`. OpenAPI, OPTIMADE, MCP, and future structured protocols compile
into the same `ToolSpec` / `EndpointSpec` model. The planner does not branch on protocol type.

Call-aware invokers may receive the validated `ToolCall` when a protocol needs selected fields at
transport time. The executor still owns schema, policy, retry, and binding-drift enforcement.

### 14. Decision models must remain bounded and non-authoritative

`DecisionBackend` receives a finite set of locally generated option IDs. Unknown IDs, duplicate
selections, out-of-range/non-finite scores, and malformed results fail closed. Jev / TypeSafe System
One is an optional provider adapter; low-confidence valid choices may abstain and deterministic
fallback remains locally controlled.

Decision providers never construct `ToolCall` objects and never receive execution credentials or
authority. For bounded field selection, providers receive only declared non-identifier output
fields; identifier fields are preserved locally and cannot be removed by the provider. For evidence
sufficiency, local schema metadata must already satisfy requested provenance/license/unit/source-type
requirements before the provider is consulted; the provider can then only preserve or veto the
call and cannot upgrade missing evidence. Jev additionally does not receive
`DecisionOption.metadata`.

### 15. Remote runtime responses need memory bounds

Schema and documentation fetches were already bounded, and OPTIMADE runtime execution used a bounded
reader. OpenAPI runtime execution now uses the same posture: responses are streamed and capped at
16 MiB by default, checking both declared `Content-Length` and bytes actually received before
JSON/text decoding.

### 16. Unsupported OpenAPI semantics must be visible

OpenAPI parsing success does not imply perfect semantic fidelity. Imported OpenAPI tools therefore
carry a machine-readable compatibility report that marks partial or unsupported constructs. Same-
origin cross-document references can be explicitly bundled under bounded limits; unresolved external
references, `$id` rebasing, non-JSON-Pointer anchors, composition, cookie parameters, non-JSON
bodies, callbacks, webhooks, and server variables remain visible rather than guessed.

### 17. Authenticated MCP must preserve credential separation

MCP authentication belongs to the trusted HTTP transport/client boundary. Credentials embedded in
MCP URLs are rejected, protocol-controlled headers cannot be overridden, and custom OAuth/mTLS/
gateway behavior is injected as a trusted client factory rather than represented in tool schemas.

### 18. Runtime permission and per-call approval are separate gates

Local `ExecutionPolicy` grants category-level authority. Optional trusted approval callbacks gate
individual calls after schema/policy validation and fail closed on missing, negative, or exceptional
decisions.

### 19. Execution budgets must account for retries

One logical call may produce multiple real invoker attempts. Budgets therefore count logical calls,
total attempts, remote attempts, wall-clock execution, per-tool quotas, and application-defined cost
units separately. Retries consume attempt/remote/cost budget before invocation.

### 20. Observability must not weaken payload privacy

The OpenTelemetry integration consumes typed RunEvents but intentionally exports only structural
attributes. Argument/result values, RunConfig metadata, tags, and exception messages are omitted.

### 21. Installed adapter plugins are executable code

Plugin metadata can be discovered without import. Entry-point loading requires an explicit non-empty
allowlist so installed packages are never auto-executed merely because they are discoverable.

### 22. Trusted middleware must not become transformation authority

Execution hooks run only after schema/policy/approval validation and receive detached snapshots.
Before hooks may veto by failing but cannot mutate the executable call. After hooks receive only the
validated, projected result and cannot mutate the result returned to the caller. Non-None returns
are rejected, hook errors fail closed, and after-hook failures are never retried as tool failures.

Because sync/async before hooks may wait while local state changes, SchemaRouter refreshes current
schema and binding state after hooks complete before invocation.

### 23. Trace replay must never become execution authority

Persistent traces store validated `RunEvent` envelopes. Replay returns detached historical events
only and never invokes the planner, executor, network, or tool bindings. Sequence gaps, identity
mismatches, timestamp regressions, corrupt stored JSON, and events appended after a terminal event
fail closed.

The trace database preserves the privacy level of the source event stream: default redacted events
remain structural, while an explicit `include_payloads=True` choice persists payload-bearing data
and therefore creates an application-managed sensitive-data store.

### 24. Schema drift needs explanation without compatibility bypass

Exact fingerprints remain the execution boundary, but a bare mismatch is operationally opaque.
`compare_endpoint_specs()` and `compare_tool_specs()` therefore classify trusted snapshot changes
as identical, compatible, breaking, or security-review changes. The classifier is deliberately
conservative for JSON Schema.

Compatibility reports are diagnostic only. They never permit a stale `ToolCall` or invoker binding
to execute without replanning/rebinding against the current fingerprint.

### 25. Category-wide permission can be too broad

The original `allow_mutations` / `allow_destructive` switches remain safe defaults, but production
applications may need narrower authority. Ordered local `PolicyRule` values can allow, deny, or
require approval for a bounded `tool.endpoint` pattern and optional side-effect predicates.

Rules are trusted application configuration. Remote schemas, descriptions, decision backends, and
model output cannot create or alter them.

### 26. Planning explanations must be auditable, not chain-of-thought

Each planned call may carry a structured `PlanExplanation` containing deterministic score
components, field-retention reasons, ignored undeclared arguments, and whether a bounded decision
backend selected the candidate.

These are locally observable routing facts. SchemaRouter does not expose or attempt to reconstruct
private model reasoning.

### 27. Descriptive metadata must not become hidden execution authority

Adversarial review found that adapter/runtime behavior can accidentally depend on values stored in
ordinary `metadata`, while fingerprints intentionally exclude that bag. If execution or policy
reads such a value, the runtime meaning can change without producing schema/binding drift.

SchemaRouter therefore separates:

- ordinary `metadata`: descriptive/inspection data only;
- `EndpointSpec.execution_metadata`: fingerprinted endpoint runtime semantics;
- `ToolSpec.execution_metadata`: fingerprinted transport/binding identity;
- `ToolSpec.remote`: fingerprinted local/remote authority classification.

Built-in adapters mirror some values into ordinary metadata for backward-compatible inspection, but
runtime code reads the fingerprinted contract fields. Legacy persisted built-in metadata is migrated
into those fields during model validation.

Planner-generated `ToolCall` values also pin the current tool fingerprint, so changing transport
origin or local/remote classification invalidates an already-compiled plan even after a trusted
rebind.

### 28. Parallel execution must not become orchestration

`parallel_read_only` is limited to flat plans whose calls all preflight successfully and have
`read_only is True`. Schema, binding, and policy validation happen before tasks are launched, and
all tasks share the same run budget and concurrency bound.

Dependencies, branching, checkpointing, write coordination, compensation, and DAG semantics remain
outside the core and belong to surrounding orchestration frameworks.

## Core invariants

1. A plan cannot call an unregistered tool or endpoint.
2. A plan cannot pass undeclared parameters.
3. Required parameters are recomputed at execution; a forged plan cannot suppress them.
4. Arguments must satisfy the current endpoint input JSON Schema.
5. Requested projection fields must be declared logical field IDs from the current endpoint; nested
   wire paths come only from trusted `FieldSpec.path` metadata.
6. Raw tool output must satisfy the current endpoint output JSON Schema before projection.
7. A stale endpoint fingerprint cannot execute.
8. A stale invoker binding cannot execute after tool replacement.
9. Remote metadata cannot grant authorization.
10. Known remote mutations/destructive operations require local policy opt-in.
11. Unclassified remote MCP operations require local policy opt-in.
12. Schema-fetch credentials cannot cross an origin redirect or an explicitly enabled external-ref
    fetch boundary.
13. Cross-origin OpenAPI server declarations and external-ref targets require explicit local
    authority; external-ref targets are same-origin only in the built-in resolver.
14. Runtime API secrets are not model-visible tool parameters.
15. Ambiguous output selection favors recall over aggressive pruning.
16. Automatic retries apply only to endpoints trusted as read-only unless local code opts in.
    Built-in OpenAPI/OPTIMADE transports fail fast on known non-transient HTTP and deterministic
    response-contract failures; trusted custom invokers can raise `NonRetryableInvocationError`
    to opt a failure out of the retry loop.
17. Run-event arguments and result payloads are redacted unless payload tracing is explicitly enabled.
18. Optional framework integrations call back through the same executor boundary rather than bypassing policy or validation.
19. Optional decision providers can select only locally offered option IDs and cannot grant execution authority.
20. OpenAPI runtime responses are bounded before decoding, including when Content-Length is absent or misleading.
21. MCP runtime credentials remain inside trusted transport configuration and are never planner-visible.
22. Calls requiring local approval fail closed if approval is absent, denied, or errors.
23. Execution budgets are checked before each logical call and real invoker attempt; async
    approval callbacks, execution hooks, invocations, and retry backoff are bounded by the remaining
    wall-clock budget. Synchronous trusted callbacks are checked immediately after returning.
24. Adapter plugins are never auto-imported from discovery alone.
25. OpenTelemetry export omits payload values and exception messages by design.
26. OpenAPI compatibility limitations are surfaced explicitly rather than silently guessed.
27. Candidate indexing may reduce scorer work but must preserve exhaustive deterministic planner recall.
28. Execution hooks receive detached snapshots and cannot transform calls or results.
29. Hook failures fail closed and never create additional tool invocation attempts.
30. Schema compatibility analysis never bypasses exact plan/binding fingerprint validation.
31. Fine-grained policy rules exist only in trusted local configuration and cannot be supplied by
    models or remote capability metadata.
32. Structured planning explanations contain deterministic/runtime-visible signals only, not model
    chain-of-thought.
33. Parallel execution requires every call to preflight as explicitly read-only and shares one run
    budget across concurrent calls.
34. Ordinary descriptive metadata cannot grant policy authority or alter built-in transport
    semantics; execution-affecting values live in fingerprinted contract fields.
35. Planner-generated calls pin both endpoint and tool fingerprints, and remote/runtime-sensitive
    legacy calls without a tool fingerprint fail closed.

## Current extension backlog

- trusted local classification for individual MCP tool side effects and richer MCP retry semantics;
- OpenAPI `$id`/anchor-aware resolution and richer composition-aware planning/execution;
- non-object request-body ergonomics and typed array-element projection if justified;
- organization-specific policy/approval and license/provenance extensions;
- compensation, transactions, and distributed execution;
- distributed/remote registry implementations beyond the built-in SQLite persistence;
- multi-page and client-rendered documentation crawling;
- additional trusted trace/export sinks;
- dated live-provider benchmark evidence and compatibility dashboards.

These are extension layers. They should not weaken the core fail-closed contracts above.

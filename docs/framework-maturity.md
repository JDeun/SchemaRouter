# Framework maturity matrix

SchemaRouter is intentionally narrower than LangChain. The goal is not to reproduce a general
agent framework; it is to make schema-aware tool planning and execution production-grade and easy
to embed in larger ecosystems.

This document tracks framework-level maturity rather than research metrics.

| Capability | Current main | Direction |
| --- | --- | --- |
| Typed tool / endpoint / parameter / field contracts | Implemented | Core invariant |
| Natural-language planning | Implemented | Improve candidate indexing at scale |
| Sync / async invocation | Implemented | Stable public surface |
| Batch execution | Implemented | Add batch-as-completed later |
| Result streaming | Implemented | Add parallel-call streaming later |
| Typed event streaming | Implemented | Add callback exporters / trace stores |
| Input / output / config schema introspection | Implemented | Keep machine-readable |
| Retry policy | Implemented | Add provider-specific transient error classifiers |
| Python callable tools | Implemented | Improve docstring parameter descriptions |
| Structured-source adapter registry | Implemented in v0.2 | Add third-party plugin packaging conventions |
| OpenAPI ingestion | Implemented common subset | Add external refs / composition |
| OPTIMADE ingestion and execution | Implemented in v0.2 | Add provider federation / index meta-database traversal |
| MCP ingestion and execution | Implemented | Add authenticated custom transports |
| Human-readable API documentation | Grounded proposal flow | Add multi-page/browser discovery |
| Runtime policy | Implemented | Add per-call approval / budgets / quotas |
| Runtime JSON Schema validation | Implemented | Add richer nested projection |
| LangChain / LlamaIndex integrations | Implemented optional adapters | Add LangGraph-native nodes and ecosystem listings |
| Bounded decision backends | Implemented, opt-in and experimental | Add provider adapters behind the finite-option contract |
| Framework callbacks / exporters | Typed redacted event stream | Add callback manager / OpenTelemetry exporters |
| Middleware interception | Policy-specific only | Add trusted before/after hooks |
| Composition / DAG runtime | Out of scope for core | Integrate with LangGraph rather than duplicate it |
| Persistence / checkpoints | Out of scope for core | Delegate to orchestration layer |
| HTTP serving layer | Not implemented | Consider optional server package |
| Pluggable registry boundary | Implemented via `ToolRegistry` protocol | Add persistent implementations |
| Release / compatibility policy | Implemented | Enforce during RC reviews |
| Package artifact CI | Implemented | Keep wheel/sdist metadata checks blocking |
| Documentation site | Implemented with MkDocs Material | Keep strict docs build blocking |
| Integration certification suite | Implemented baseline | Extend the live compatibility matrix |

## What SchemaRouter should copy from mature frameworks

### 1. One execution vocabulary

A framework becomes easier to learn when every major component follows the same execution verbs.
SchemaRouter therefore exposes:

- `invoke` / `ainvoke`
- `batch` / `abatch`
- `stream` / `astream`
- `astream_events`
- `with_config`

These methods do not bypass planner, policy, schema validation, or binding-drift checks.

### 2. Introspection as a public contract

`input_schema`, `output_schema`, and `config_schema` are public machine-readable interfaces.
They are intended for serving layers, UI generation, testing, and framework integrations.

### 3. Tool authoring must be cheap

Python callables can be registered directly through `add_callable()` and optionally annotated with
`@schema_tool`. OpenAPI, OPTIMADE, and MCP are built-in structured ingestion paths, while
`AdapterRegistry` keeps additional protocols out of the core planner.

### 4. Integrations should be optional

The core package should not become a dependency aggregator. Ecosystem bridges such as LangChain and
LlamaIndex belong behind optional extras and lazy imports.

### 5. Observability must not weaken privacy

Event payloads are redacted by default. Arguments and result payloads appear only when
`RunConfig(include_payloads=True)` is explicitly selected.

## What SchemaRouter should not copy

- a general chat/message abstraction;
- prompt template ecosystems;
- model-provider wrappers unrelated to schema planning;
- memory/checkpoint systems;
- a second graph runtime;
- hidden coercion that weakens schema contracts.

Those concerns are better handled by surrounding frameworks. SchemaRouter should remain a focused
compiler/runtime boundary for tool schemas.

## Next maturity gates

### Gate A — published alpha baseline

- public API examples;
- live OpenAPI compatibility tests;
- live MCP compatibility tests;
- API versioning/deprecation policy;
- release checklist;
- MIT license metadata and release artifact verification.

### Gate B — ecosystem-ready

- runnable LangChain and LlamaIndex examples;
- published ecosystem compatibility and maintenance policy;
- upstream ecosystem listing/discussion requests;
- callback/exporter API;
- OpenTelemetry-compatible trace exporter;
- LangGraph-native integration;
- trusted local MCP side-effect classification;
- richer OpenAPI references and schema composition.

### Gate C — production operations

- persistent registry implementations behind the `ToolRegistry` protocol;
- quotas/cost budgets;
- per-call human approval;
- replayable execution traces;
- benchmark and compatibility dashboard.

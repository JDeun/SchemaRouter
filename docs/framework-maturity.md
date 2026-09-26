# Framework maturity matrix

SchemaRouter is intentionally narrower than LangChain. The goal is not to reproduce a general
agent framework; it is to make schema-aware tool planning and execution production-grade and easy
to embed in larger ecosystems.

This document tracks framework-level maturity rather than research metrics.

| Capability | Current main | Direction |
| --- | --- | --- |
| Typed tool / endpoint / parameter / field contracts | Implemented | Core invariant |
| Natural-language planning | Deterministic scoring + exact-recall candidate index cached by registry version | Add approximate/remote retrieval only behind an explicit contract if future scale requires it |
| Sync / async invocation | Implemented | Stable public surface |
| Batch execution | Implemented, including completion-order APIs | Stable public surface |
| Result streaming | Sequential by default + explicit read-only parallel completion streaming | Keep dependency/DAG semantics out of core |
| Typed event streaming | Implemented | Extend exporter ecosystem without exposing payloads |
| Input / output / config schema introspection | Implemented | Keep machine-readable |
| Retry policy | Read-only gate + explicit non-retryable invocation marker + built-in OpenAPI/OPTIMADE HTTP classification | Extend protocol-specific classifiers only where recovery semantics are well-defined |
| Python callable tools | Implemented | Improve docstring parameter descriptions |
| Structured-source adapter registry | Implemented with explicit entry-point plugins | Expand certified third-party adapters |
| OpenAPI ingestion | Common subset + operation-over-path parameter overrides + default path/query/header serialization + flattened object bodies + generic typed JSON root bodies + discriminator-aware tagged oneOf bodies + schema-less body reporting + spec-ignored header filtering + collision-safe generated operation names + multi-2xx JSON/no-content response validation + local refs + opt-in bounded same-origin cross-document refs + static same-origin $id/$anchor resolution + OpenAPI 3.0 nullable normalization + allOf object flattening + oneOf/anyOf response-field discovery + compatibility report | Keep dynamic refs, non-default parameter styles, and automatic variant selection fail-closed; expand only behind typed contracts |
| OPTIMADE ingestion and execution | Implemented in v0.2 | Add provider federation / index meta-database traversal |
| MCP ingestion and execution | Implemented with authenticated/custom transport boundary | Expand OAuth/gateway examples |
| Human-readable API documentation | Grounded proposal flow | Add multi-page/browser discovery |
| Runtime policy | Category defaults + ordered operation-scoped allow/deny/approval rules + execution budgets | Add external organization policy adapters only behind the trusted local boundary |
| Runtime JSON Schema validation / projection | Full raw validation + explicit nested object projection paths + trusted server-side field selectors | Add typed array-element projection only if needed |
| Schema drift analysis | Conservative endpoint/tool compatibility reports; exact fingerprints still gate execution | Add CI/reporting integrations without weakening drift rejection |
| Planning explanations | Structured score components, field-selection reasons, ignored-argument records, and decision-selection source | Keep explanations structural; never expose model chain-of-thought |
| In-plan concurrency | Explicit flat `parallel_read_only` fan-out with preflight validation, completion streaming, and shared budgets | Keep DAG/dependency/write orchestration out of core |
| Provider/access fallback | Precompiled read-only same-provider/cross-provider routes with semantic field compatibility and typed fallback events | Expand provider federation only through explicit contracts |
| Scientific field contracts | Explicit JSON value shape, optional exact units, affine canonical normalization, exact trusted qualifiers, qualifier-aware routing, and fail-closed fallback compatibility | Keep ontology/unit inference outside core; add richer scientific semantics only through explicit trusted contracts |
| Provider parameter aliases | Trusted exact/alias binding with ambiguity fail-closed behavior and independent fallback compilation | Keep model-generated parameter remapping out of the execution boundary |
| Access health | Finite passive cooldown + optional trusted background probes with early reopen | Integrate external health sources without model authority |
| LangChain / LangGraph / LlamaIndex integrations | Implemented optional adapters and native graph node | Expand ecosystem listings |
| Bounded decision backends | Semantic candidate recall, broad capability-fit, operation-fit, same-tool endpoint disambiguation, candidate/field selection, and conservative evidence-sufficiency surfaces; provider-neutral callable/embedding + optional Jev/Laya/Ollama, all opt-in | Gather live decision evidence and keep model authority bounded |
| Jev / TypeSafe decision provider | Implemented optional adapter | Gather live workload evidence before claiming quality gains |
| Local Laya decision provider | Optional local choice adapter with auto language routing, confidence abstention, lazy/preloaded checkpoints, and shared benchmark support | Gather checkpoint/hardware-specific evidence before choosing defaults |
| Local Ollama decision provider | Implemented over structured-output HTTP API | Benchmark specific local models/hardware before quality claims |
| Decision benchmark harness | 1,200-case multilingual v2 stress corpus plus separate v3 capability-fit, v4 endpoint-disambiguation, v5 operation-fit calibration plus consumed v6/v7/v8 diagnostics and the consumed one-shot v9 alias-aware operation holdout; JSON/CSV metrics + Wilson intervals + single-run and multi-run self-contained HTML summaries | Gather dated live-provider evidence and add fresh holdouts when a consumed test set can no longer support an untouched claim |
| Framework callbacks / exporters | Typed redacted events + optional OpenTelemetry exporter | Add additional trusted sinks as needed |
| Middleware interception | Trusted ordered before/after execution hooks with detached snapshots | Add organization-specific hook libraries only when needed |
| Composition / DAG runtime | Out of scope for core | Integrate with LangGraph rather than duplicate it |
| Replayable run trace persistence | SQLite append-only event traces + non-executing replay | Add alternate trusted stores/export paths as needed |
| Persistence / checkpoints | Workflow checkpoints remain out of scope | Delegate orchestration state to LangGraph or another runtime |
| HTTP serving layer | Not implemented | Consider optional server package |
| Pluggable registry boundary | `ToolRegistry` protocol + transactional `SQLiteRegistry` | Add distributed/remote implementations only when needed |
| Release / compatibility policy | Implemented | Enforce during RC reviews |
| Package artifact CI | Implemented with clean wheel/sdist smoke, public-surface consumer acceptance scenarios, built-wheel optional-extra resolution/import smoke, framework-example execution, provenance, and SPDX SBOM attestations | Keep artifact verification blocking |
| Security automation | Weekly/PR dependency audit + push/PR/scheduled CodeQL + OpenSSF Scorecard + immutable Action pins | Triage findings without weakening fail-closed runtime policy |
| Documentation site | Implemented with MkDocs Material | Keep strict docs build blocking |
| Integration certification suite | Implemented baseline + retained machine-readable OpenAPI/OPTIMADE smoke artifacts | Extend the live compatibility matrix |

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

The core package should not become a dependency aggregator. Ecosystem bridges and decision
providers belong behind optional extras and lazy imports.

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

### Gate A — published non-prerelease baseline

The package, documentation, release automation, deterministic compatibility tests, and public
OpenAPI/OPTIMADE smokes are in place.

### Gate B — ecosystem-ready

Completed locally:

- runnable LangChain, LangGraph, and LlamaIndex examples;
- published ecosystem compatibility and maintenance policy;
- optional Jev decision provider with adversarial contract tests;
- optional local Laya decision provider with bounded choice validation and shared benchmark support;
- provider-neutral embedding-similarity decision backend with threshold/margin abstention and
  malformed-vector fail-closed validation;
- bounded field-selection contract with identifier preservation and deterministic fallback;
- conservative evidence-sufficiency contract with local provenance/license/unit/source-type precheck
  and provider veto-only semantics;
- provider-neutral decision benchmark harness;
- exact-recall candidate index with registry-version cache invalidation and exhaustive parity tests;
- 1,200-case multilingual/adversarial v2 benchmark corpus plus separate frozen calibration/holdout corpora for capability-fit, endpoint disambiguation, and operation-fit evaluation;
- OpenAPI compatibility reporting;
- opt-in bounded same-origin cross-document OpenAPI reference bundling;
- authenticated MCP transport boundary;
- per-call approval and per-run execution budgets;
- operation-scoped local policy rules with explicit allow/deny/approval effects;
- conservative endpoint/tool schema diff reports that never bypass fingerprint checks;
- structured planning explanations derived from deterministic/runtime-visible signals;
- flat read-only parallel fan-out with preflight validation and shared run budgets;
- field-first server-side projection contracts plus final local projection;
- bounded provider/access fallback with finite cooldown and trusted health-probe recovery;
- privacy-preserving OpenTelemetry exporter;
- explicit allowlisted third-party adapter plugins;
- property-based OpenAPI default-serialization coverage;
- self-contained decision benchmark HTML reporting and multi-run history rendering;
- retained machine-readable public OpenAPI/OPTIMADE compatibility smoke artifacts;
- public-surface consumer acceptance validation across supported Python versions, Windows,
  minimum dependencies, wheel, and sdist installs, with built-wheel MCP/Jev/OpenTelemetry
  import/initialization smoke plus LangChain/LangGraph/LlamaIndex runnable examples.

Still external or follow-up work:

- upstream ecosystem listing/discussion requests;
- broader live benchmark evidence;
- dynamic OpenAPI/JSON-Schema reference semantics and automatic planner-side schema-variant selection.

### Gate C — production operations

Implemented locally:

- deterministic call/attempt/remote/time/cost budgets;
- trusted sync/async per-call approval;
- OpenTelemetry span export from the redacted event stream;
- authenticated MCP/custom client-factory boundary;
- explicit allowlisted adapter plugin loading;
- transactional persistent SQLite registry behind the `ToolRegistry` protocol;
- OpenAPI compatibility reports;
- transactional SQLite tool registry persistence;
- validated SQLite run-event trace persistence with non-executing replay;
- trusted sync/async before/after execution hooks with snapshot-only, fail-closed semantics;
- dependency vulnerability auditing, CodeQL scanning, OpenSSF Scorecard supply-chain analysis, signed release build provenance, and SPDX SBOM attestations;
- benchmark summary/history dashboards generated without remote assets;
- scheduled compatibility smokes retained as versioned machine-readable artifacts.

Remaining larger follow-up work:

- populate history views with dated live model/provider measurements;
- organization-specific policy/approval integrations.

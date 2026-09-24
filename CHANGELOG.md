# Changelog

All notable changes to SchemaRouter are documented here.

The project is pre-1.0 and follows the compatibility rules in
[`docs/versioning.md`](docs/versioning.md).

## Unreleased

### Added

- self-contained HTML summaries for the decision-routing benchmark, alongside the existing JSON/CSV
  outputs, with escaped metadata and no remote assets;
- multi-run benchmark history rendering with preserved run/version/corpus/hardware metadata;
- benchmark reproducibility manifests with exact source revision, corpus SHA-256, repeat count, and
  case-limit metadata, surfaced in single-run and history HTML reports;
- dependency-free 95% Wilson score intervals for routing accuracy, no-route recall, and
  category-level accuracy in benchmark JSON and HTML history views;
- machine-readable OpenAPI/OPTIMADE compatibility smoke artifacts retained from scheduled CI;
- Hypothesis-based property tests for supported OpenAPI path/query/header parameter serialization;
- automated dependency vulnerability auditing and scheduled CodeQL Python analysis;
- opt-in `DecisionPolicy.recall_on_empty` recovery for enabled bounded candidate-selection
  backends when lexical schema recall is empty, with fail-closed abstention/error behavior;
- row-level decision confidence capture and offline threshold calibration that can replay either
  deterministic fallback or final no-route behavior without repeating model inference;
- independently configurable candidate-abstention handling with compatibility-preserving
  `inherit`, plus explicit `deterministic`, `no_route`, and `error` modes, without changing
  provider-error fallback semantics;
- dependency-free public-surface consumer acceptance scenarios covering policy/approval gates,
  schema and binding drift, runtime output validation, retry/budget controls, persistence, traces,
  and dashboard generation;
- scheduled/manual compatibility smokes that force-install the latest stable SchemaRouter wheel and
  sdist from PyPI in fresh runners, run `pip check`, execute a public API scenario outside the
  checkout, and retain machine-readable reports;
- a published-framework compatibility smoke that resolves the stable LangChain/LangGraph/LlamaIndex
  extras from PyPI and executes all three bridges outside the source checkout;

### Changed

- raised the blocking branch-coverage floor from 82% to 84%;
- made the protected `package` CI check depend on both the Laya integration contract and a
  dependency vulnerability audit, so either regression blocks merge even when the repository
  ruleset predates newer job names;
- package smoke now verifies benchmark JSON and HTML artifact generation;
- package validation now executes consumer acceptance scenarios from clean wheel and sdist
  environments, installs the built wheel through its LangChain/LangGraph/LlamaIndex extras
  before running each framework example, and exercises the installed inspection/dashboard CLI
  against real persisted registry/trace artifacts;
- research benchmarking now compares Laya's lexical-only path with explicit empty-candidate recall
  on the same full corpus and hardware;
- post-release development has resumed as `0.7.0.dev0`; published `0.6.0` artifacts remain immutable.

### Security

- added a pinned OpenSSF Scorecard workflow that publishes authenticated results, retains SARIF, and
  uploads findings to GitHub Code Scanning on main and a weekly schedule;
- pinned every external GitHub Action dependency to an immutable commit SHA and added a CI invariant
  that prevents tag/branch-based Action references from returning;
- extended CodeQL to pull requests and narrowed its write permission to the analysis job;
- made the Docs workflow read-only by default and grants Pages/OIDC write access only to deployment;
- removed the dynamic event-derived checkout from the write-capable release preparation path and
  made GitHub Release publication consume trusted build artifacts without checking out release code;
- linked SECURITY.md directly to GitHub private vulnerability reporting;
- release wheel and sdist artifacts now receive GitHub/Sigstore build-provenance attestations before
  publication;
- release builds now generate a pinned-tool SPDX JSON SBOM outside the PyPI distribution directory,
  attest that SBOM against wheel/sdist artifacts, and attach the SBOM to the GitHub release.

## 0.6.0 - 2026-09-23

### Added

- spec-faithful OpenAPI default parameter serialization for path/header `simple` and query
  `form` styles across scalar, array, and object values, with serialization settings included in
  the typed parameter contract and unsupported styles/`allowReserved=true` failing closed.
- generic typed OpenAPI JSON root request bodies for explicit schemas that cannot be safely
  flattened, including arrays, scalars, nullable roots, and non-discriminated `oneOf` / `anyOf`
  compositions; root values are validated locally and transmitted without a synthetic wrapper.
- strict OpenAPI discriminated `oneOf` JSON request-body support as one typed root `body`
  parameter when every object branch requires a unique const/single-enum discriminator tag; the
  full composed schema is validated locally and transmitted as the JSON root without flattening.
- read-only operational inspection API and `schemarouter inspect` CLI for persisted SQLite
  registries and run traces, including tool/endpoint classification, schema fingerprints, parameter
  and output-field structure, trace completion/error summaries, human-readable output, and stable
  JSON output for dashboards/automation.
- live `SchemaRouter.inspect()` snapshots for analyzer, bounded-decision policy, execution
  policy, and actual invoker binding keys, plus a self-contained read-only HTML dashboard export
  backed by the same safe inspection models.
- optional local `LayaDecisionBackend` through `schemarouter[laya]`, with language-aware local
  checkpoint routing, confidence-based abstention, lazy/preloaded execution, fail-closed option-ID
  validation, trusted credential separation, and shared decision-benchmark support.

### Changed

- OpenAPI 3.0 `nullable: true` schemas with an explicit same-object `type` are normalized
  into JSON Schema type unions, including nested components and bounded external-ref bundles, so
  valid JSON null inputs/outputs are no longer false-rejected by runtime validation.
- OpenAPI response `oneOf` / `anyOf` object variants now contribute conditional
  planner-visible output fields while the original composed schema remains authoritative for raw
  runtime validation; variant request bodies remain deliberately unflattened even when executable
  through the typed root-body contract.
- opt-in bounded OpenAPI external-reference resolution now honors same-origin JSON Schema
  `$id` base-URI rebasing, nested virtual resources, and static `$anchor` fragments before
  rewriting all resolved references into the self-contained local bundle; cross-origin IDs and
  dynamic/recursive reference semantics remain fail-closed.
- promoted the 0.6 development line to the non-prerelease `0.6.0` release after the local decision-backend, operational inspection, and OpenAPI fidelity work passed the protected release gates.

### Compatibility

- no intentional public API removals are introduced relative to `0.5.0`;
- new Laya, inspection/dashboard, and typed root-body surfaces are additive and opt-in where they can affect model-assisted decisions or operational output;
- OpenAPI behavior is more spec-faithful for supported static references, nullable schemas, composed responses, root request bodies, and default parameter serialization while unsupported dynamic semantics remain fail-closed;
- the project remains pre-1.0, so later 0.x minor releases may still include deliberate documented compatibility changes.

## 0.5.0 - 2026-09-23

### Added

- public `NonRetryableInvocationError` contract for trusted invokers that can prove repeating the
  same call cannot recover safely.
- conservative built-in HTTP retry classification for OpenAPI and OPTIMADE, including fail-fast
  handling for non-transient status codes and deterministic response-contract violations.
- wall-clock-budget-aware retry backoff that stops at the remaining elapsed-time boundary instead of
  sleeping past `ExecutionBudget.max_elapsed_seconds`.
- retry delay capping now applies `max_backoff_seconds` to the initial delay as well as subsequent
  exponentially increased delays.
- elapsed-time budgets now start before per-call approval and actively bound async approval callbacks
  and before/after execution hooks, eliminating unbounded awaited middleware outside the invocation
  timeout.
- OpenAPI operation-level parameters now correctly override same-identity Path Item parameters,
  preserving the specification's `(name, in)` override semantics during schema import.
- generated OpenAPI endpoint names now remain collision-safe for valid paths that normalize to the
  same fallback token, while explicit `operationId` values are preserved unchanged.
- required supported OpenAPI JSON object request bodies now preserve body presence even when every
  flattened property is optional, sending an empty object instead of silently omitting the body.
- OpenAPI `Accept`, `Content-Type`, and `Authorization` header parameters are now ignored during
  import as required by the Parameter Object contract, keeping protocol/auth control out of planner
  arguments.
- schema-less OpenAPI JSON request bodies are no longer inferred as empty objects; they remain
  unrepresented at runtime and are surfaced explicitly as unsupported compatibility findings.
- OpenAPI success-response handling now preserves multiple 2xx JSON/no-content variants, validates
  supported payloads through a combined schema, keeps planner-visible fields across JSON variants,
  treats empty no-content successes as `None`, and scans every success response for compatibility
  findings.

### Changed

- promoted the 0.5 development line to the non-prerelease `0.5.0` release after the retry/budget
  hardening and OpenAPI fidelity pass completed the protected release gates.

### Compatibility

- no intentional public API removals are introduced relative to `0.4.0`;
- built-in OpenAPI and retry behavior is stricter or more spec-faithful only in cases that were
  previously retried, omitted, fabricated, collided, or validated against the wrong success schema;
- the project remains pre-1.0, so later 0.x minor releases may still include deliberate documented
  compatibility changes.

## 0.4.0 - 2026-09-22

### Added

- trusted ordered sync/async before/after execution hooks with detached schema/call/result
  snapshots, non-transforming None-only return contracts, post-await schema/binding refresh, and
  fail-closed non-retryable hook errors.
- explicit opt-in bounded same-origin OpenAPI cross-document `$ref` bundling with schema-header
  credential confinement, redirect/origin enforcement, depth/document/aggregate-byte budgets,
  complete-document JSON/YAML parsing, cycle caching, runtime schema preservation, and fail-closed
  handling for `$id` rebasing and non-JSON-Pointer anchors.
- exact-recall candidate indexing cached by registry version, with exhaustive-mode parity tests,
  stable-snapshot rebuilds, synthetic scorer-call benchmarking, and no approximate pruning.
- conservative bounded `evidence_sufficiency` decision surface with deterministic local
  provenance/license/unit/source-type prechecks, provider veto-only semantics, sync/async support,
  abstention/error fallback policy, and no ability to upgrade missing evidence.
- explicit `FieldSpec.path` nested-object projection with logical field IDs, full raw-output
  validation before extraction, overlap/collision fail-closed validation, planner path-token
  matching, local projection enforcement for nested paths, and detached projected values.
- bounded `field_selection` decision surface that exposes only declared non-identifier output
  fields, always preserves identifier fields locally, caps selections by the deterministic
  projection width, recomputes evidence from the final field set, and supports sync/async
  deterministic fallback.
- append-only `SQLiteRunTraceStore` with strict sequence/run/timestamp invariants, corruption
  fail-closed validation, direct `astream_events(..., trace_store=...)` persistence, redaction-
  preserving storage, and non-executing historical replay.
- transactional `SQLiteRegistry` persistence with monotonic version retention, deterministic tool
  ordering, atomic batch writes, JSON-only storage, corruption/key-mismatch fail-closed validation,
  and no persistence of trusted invokers or credentials.
- local Ollama bounded-decision backend using structured JSON Schema output, local option-ID
  revalidation, sync/async HTTP paths, redirect rejection, token metadata capture, adversarial
  mock-transport tests, and shared benchmark-harness support.
- provider-neutral `EmbeddingDecisionBackend` with sync/async embedding callables, cosine ranking,
  bounded top-k selection, similarity/margin abstention, malformed-vector fail-closed validation,
  and common benchmark-harness support.
- OpenAPI planner fidelity for chained local references, local Path Item references, safe
  same-document URI-reference normalization during URL ingestion, and object property/required
  discovery through `allOf` while preserving runtime schema validation.
- native LangGraph `StateGraph` integration through `schemarouter[langgraph]`, with sync/async
  execution, checkpoint-friendly result serialization, custom state-to-request adaptation, contract
  tests, and a runnable example.

### Changed

- promoted the 0.4 development line to the non-prerelease `0.4.0` release after the persistence,
  bounded-decision, OpenAPI, LangGraph, and execution-hook surfaces passed the required release gates.

### Compatibility

- no intentional public API removals are introduced relative to `0.3.0`;
- new operational surfaces remain opt-in where they can affect persistence, model-assisted decisions,
  cross-document network access, or execution interception;
- the project remains pre-1.0, so later 0.x minor releases may still include deliberate documented
  compatibility changes.

## 0.3.0 - 2026-09-22

### Changed

- promoted the 0.3 line to the first non-prerelease release after the 0.3.0a1 validation cycle;
- standard PyPI installation no longer requires `--pre`;
- package maturity metadata now identifies the project as beta while retaining the documented
  pre-1.0 compatibility policy;
- GitHub Pages deployment and protected-main required-check enforcement are now active repository
  controls.

### Compatibility

- no intentional public API changes were introduced relative to 0.3.0a1;
- the 0.x line remains pre-1.0, so later minor releases may still include deliberate, documented
  compatibility changes.

## 0.3.0a1 - 2026-09-22

### Added

- provider-neutral bounded `DecisionBackend` contracts with deterministic fallback;
- optional `JevDecisionBackend` backed by TypeSafe System One through `schemarouter[jev]`;
- optional LlamaIndex `FunctionTool` integration;
- runnable LangChain and LlamaIndex integration examples enforced in CI;
- provider-neutral decision-routing benchmark harness covering accuracy, abstention, latency,
  token usage, and optional cost estimation;
- explicit ecosystem compatibility matrix and integration maintenance policy;
- Korean project overview in `README.ko.md`;
- Python 3.13 and 3.14 core CI coverage;
- a non-blocking Python 3.15 release-candidate preview;
- a Windows + Python 3.14 smoke surface;
- a Pyright static-type gate for the typed package surface;
- full-suite branch-coverage reporting with an 82% blocking floor;
- declared lower-bound runtime dependency testing;
- clean wheel and sdist installation smoke tests;
- a checked-in 144-case multilingual/adversarial decision-routing corpus with JSON/CSV output,
  category metrics, invalid-plan rate, abstention/fallback tracking, and p50/p95 latency;
- machine-readable OpenAPI compatibility reports for partial/unsupported constructs;
- authenticated MCP trusted-header and custom client-factory transport boundaries;
- trusted sync/async per-call approval callbacks;
- per-run execution budgets for logical calls, attempts, remote attempts, elapsed time, per-tool
  quotas, and application-defined cost units;
- optional privacy-preserving OpenTelemetry run/tool span export;
- explicit allowlisted third-party adapter plugins through `schemarouter.adapters` entry points.

### Changed

- release preparation now uses explicit PEP 440 release versions while normal post-release
  development returns to a `.dev0` version;
- release automation now derives version, release title, release-note path, prerelease state, and
  artifact verification from `pyproject.toml` instead of hard-coded release literals;
- release publication now consumes a successful current-`main` CI result, verifies or creates the
  annotated version tag, and clean-installs both wheel and sdist artifacts before publication;
- superseded pull-request CI runs are cancelled automatically to avoid stale validation consuming
  runner capacity;
- releasable `main` commits are automatically published by the top-level Release workflow only
  after green CI, current-head verification, release-note/changelog validation, and duplicate-tag
  checks; existing unpublished tags may be resumed only from a compatible ancestor SHA.

### Security

- OpenAPI runtime responses are now streamed through a bounded reader with a 16 MiB default limit,
  enforcing the bound both from declared `Content-Length` and actual bytes received;
- Jev option IDs are validated before confidence-based abstention, so unknown IDs always fail
  closed;
- Jev credentials remain SDK client configuration and are never placed in model state;
- `DecisionOption.metadata` is not forwarded to Jev;
- provider failures can deterministically fall back without weakening execution policy;
- MCP credentials are rejected in URLs and remain outside tool/planner metadata;
- MCP protocol-controlled headers cannot be overridden through trusted runtime headers;
- adapter entry points are metadata-only during discovery and are never auto-imported;
- OpenTelemetry export omits payload values, RunConfig metadata, tags, and exception messages;
- approval callback failures and execution budget exhaustion fail closed.

## 0.2.0a1 - 2026-09-20

### Added

- pluggable structured-source `AdapterRegistry` with explicit and priority-based auto discovery;
- OPTIMADE v1 discovery through base and entry-type info endpoints;
- OPTIMADE field-aware execution that maps planned fields to `response_fields`;
- call-aware invoker support for protocol adapters that need the full `ToolCall`;
- typed tool, endpoint, parameter, response-field, plan, and result contracts;
- namespaced versioned registry;
- schema-aware planning with recall-preserving field projection;
- provider-neutral model-assisted query analysis;
- OpenAPI 3.x URL ingestion and guarded HTTP execution;
- MCP tool discovery and execution;
- evidence-grounded proposals for human-readable API documentation;
- runtime JSON Schema validation for arguments and raw outputs;
- schema and invoker-binding drift detection;
- fail-closed execution policy for mutations, destructive calls, and unclassified remote tools;
- Runnable-style `invoke`, `batch`, `stream`, and typed event APIs;
- run configuration, concurrency control, and safe retry policy;
- typed Python callable registration with `@schema_tool`;
- optional LangChain `StructuredTool` integration;
- framework maturity, architecture, release, and versioning documentation;
- MIT licensing and package metadata;
- MkDocs Material documentation site with guides, recipes, and generated API reference;
- SchemaRouter brace-and-routing-hub brand system with light/dark marks, lockups, favicon, and
  social preview source artwork.

### Security

- separated schema-fetch credentials from runtime API credentials;
- restricted schema redirects and runtime API origins;
- blocked model/tool control of sensitive runtime headers;
- redacted event payloads by default;
- prevented automatic retries for non-read-only calls.

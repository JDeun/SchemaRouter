# Changelog

All notable changes to SchemaRouter are documented here.

The project is pre-1.0 and follows the compatibility rules in
[`docs/versioning.md`](docs/versioning.md).

## Unreleased

## 0.17.0 - 2026-10-07

### Added

- added declarative authorization-policy loading and privacy-safe authorization audit events with
  run correlation, opaque principal audit identifiers, redacted data-scope summaries, and consistent
  native/LangChain/LlamaIndex execution-boundary coverage;
- added native database schema-refresh lifecycle management and opt-in adaptive routing/session
  context primitives while keeping execution authority local and schema-bound;
- added host-controlled egress policy, bounded trace retention/pruning, bounded schema complexity,
  and explicit compatibility dispatch for native/vendor integrations;
- added reproducible external-validation infrastructure for shared router benchmarks, including
  frozen protocol packages and pinned SmartMCP development smoke coverage.

### Changed

- decomposed the large runtime facade into dedicated provider-registration, trusted-rebinding,
  native-schema-lifecycle, default-policy and compatibility components while preserving the public
  SchemaRouter facade;
- decomposed the planner into explicit immutable planning-context, candidate, primary-selection,
  fallback-selection and final-plan-assembly stages so one registry snapshot is used end-to-end;
- moved native vector/graph/record provider construction behind registration registries so backend
  additions no longer require hard-coded central runtime dispatch;
- reworked CI qualification around immutable package artifacts, blocking deterministic compatibility
  checks, per-module native-adapter coverage ratchets, exact-main post-merge qualification,
  documentation/API contract checks and dependency caching.

### Fixed

- propagated PrincipalContext/DataScope through exported LangChain and LlamaIndex tools and preserved
  principal context through parallel preflight paths;
- made multi-capability/provider registration, registry/binding publication, shared execution-budget
  reservations and schema-refresh health transitions failure-atomic;
- stopped router-owned native schema watchers during shutdown and invalidated stale/in-flight refresh
  state consistently across replacement and unregister paths;
- classified indeterminate offloaded mutation outcomes, post-invocation hook failures and trace
  persistence failures without silently converting them into successful executions;
- removed event-loop blocking and affinity hazards from synchronous remote I/O, trace persistence,
  health probes and sync wrappers;
- hardened concurrent tool-span identity, capability publication, semantic-equivalence handling,
  trace replay ordering and graph traversal behavior.

### Security

- revalidated authorization at retry and final approval boundaries, made approval requirements
  additive to side-effect authority, and failed closed when trusted vector/graph/data-scope filters
  cannot be enforced;
- centralized trusted HTTP-header validation and enforced host-owned network egress policy;
- redacted sensitive trace payloads before event sinks and bounded persistent/adaptive checkpoint,
  collection and administrative-document decoding work;
- bounded runtime JSON-Schema evaluation and untrusted schema structural complexity to limit
  pathological CPU/memory use;
- hardened SQLite backup destination creation and persisted-document parsing against races and
  unbounded resource consumption.

### Compatibility and migration

- no intentional breaking change is introduced to the documented retrieval/planning/execution
  facade; refactored internals remain behind compatibility delegates and lazy exports;
- some invalid, ambiguous or unenforceable states that could previously proceed are now rejected
  earlier by stricter fail-closed security/correctness checks;
- no new execution authority is reconstructed from persisted artifacts or schema refresh state;
- active Research 0.14 experiments remain frozen separately from the 0.17.0 product code and are not
  release claims.

## 0.16.0 - 2026-10-04

### Added
- added a native caller-owned FalkorDB property-graph adapter with graph/label/relationship/property discovery, read-only `ro_query()` traversal, and existing principal graph-scope enforcement;

- expanded native vector-store coverage with caller-owned Pinecone, Weaviate, Chroma,
  PostgreSQL/pgvector adapters, preserving bounded search, explicit
  schema/dimension handling and trusted principal-derived metadata filters;
- added caller-owned native record-store adapters for MongoDB, Elasticsearch/OpenSearch,
  DynamoDB, Azure Cosmos DB, Couchbase, ClickHouse and InfluxDB, compiling vendor discovery/query
  shapes into the bounded record contract without exposing raw vendor query languages to model output;
- added caller-owned native graph/RDF adapters for Neo4j, Amazon Neptune Database/Analytics,
  ArangoDB, and SPARQL 1.1 endpoints, translating vendor SDK/protocol shapes into the bounded graph
  contract without exposing raw query languages to model output;
- added native caller-owned Qdrant and Milvus vector backends with collection/schema
  discovery, bounded query normalization, explicit multi-vector selection, and trusted metadata
  filtering while keeping vendor credentials and clients outside model-visible contracts;
- added unified principal data scopes across relational, vector, record-store and graph/RDF
  adapters, including pre-scoring field non-disclosure, trusted principal-derived row/tenant
  predicates, graph relationship/hop restrictions, and execution-boundary revalidation;
- added a provider-neutral non-relational record-store contract covering document, search,
  key-value and time-series sources with schema discovery, exact-match filters, optional bounded
  text/time queries, field projection, and principal-aware source non-disclosure without exposing
  raw vendor query DSLs;
- added a provider-neutral property-graph/RDF capability contract with graph schema discovery,
  relationship whitelisting, bounded traversal depth/result limits, field projection, and
  principal-aware graph non-disclosure without exposing arbitrary Cypher/Gremlin/SPARQL execution;
- added a provider-neutral vector-store capability contract with collection discovery, trusted
  host embedding, dimension validation, bounded similarity search, field projection, and
  principal-aware collection non-disclosure while keeping vendor clients and credentials outside
  model-visible contracts;
- added schema-introspected read-only database onboarding through dependency-free SQLite connections
  and caller-owned SQLAlchemy Engines, compiling tables/views/columns into typed capabilities while
  keeping credentials and live connection state outside model-visible contracts; added the optional
  `database` extra and release-blocking integration coverage;
- added safe unknown-provider discovery proposals through `discover_provider()` with explicit
  inspect/approve registration, ambiguous service-family hints, caller-supplied trusted discovery
  backends, and digest-bound approval that never grants execution authority directly;
- added host-supplied principal authorization with deny-by-default RBAC/ABAC rules over roles,
  departments, teams, attributes, provider/access-mode and capability operations, including
  non-disclosure before retrieval and execution-boundary revalidation while preserving the stable
  unscoped retrieval facade.

## 0.15.0 - 2026-10-03

### Added

- expanded provider-first onboarding acceptance across live OpenAPI and OData providers plus
  provider-profile-routed GraphQL, OpenRPC and MCP reference execution, with deterministic coverage
  that every default URL-backed adapter kind flows through the same `add_provider()` path;
- added provider-first onboarding through `resolve_provider()` / `add_provider()`, with built-in
  acceptance profiles for Materials Project, Crossref, and Tavily while preserving the existing
  protocol-neutral adapter and trusted-secret boundaries;
- added explicit state-conditioned corrective retrieval through
  `reretrieve_state_aware()` / `areretrieve_state_aware()` without changing the stable
  `retrieve()` / `aretrieve()` facade;
- added indexed and incremental capability dependency-graph construction, deterministic SCC
  analysis, bounded cycle witnesses, and a 1k/10k/50k sparse graph benchmark;
- added atomic compare-and-swap capability snapshot publication with validated incremental rebuild,
  full-rebuild fallback, source provenance, and predecessor preservation on failure;
- versioned portable capability artifacts and snapshot documents, including deterministic legacy
  migration, semantic-integrity validation, and non-overwriting inspect/migrate CLI commands;
- added unified privacy-safe capability decision traces with compact/detailed rendering,
  `router.inspect(...)`, CLI inspection, and HTML dashboard integration.

### Fixed

- fixed OPTIMADE streamed compressed-response reconstruction uncovered by the live Materials Project
  provider-first acceptance smoke.

### Compatibility and migration

- the stable `retrieve(request, *, k=5)` / `aretrieve(request, *, k=5)` signatures remain
  unchanged; state-aware filtering and corrective backfill are explicit additive APIs;
- capability artifact 1.0 documents migrate to 1.1 with legacy edges preserved as `external`
  rather than being silently promoted to derived authority;
- raw pre-envelope `CapabilityGraphSnapshot` JSON remains readable and migrates into the versioned
  snapshot document envelope after validating its existing snapshot ID.

## 0.14.0 - 2026-10-02

### Added

- added a protocol-neutral, read-only capability explorer that exposes registered tools, endpoints,
  parameters, output fields, units/qualifiers, fingerprints, binding state, authentication
  requirements, health state, and schema-watch status without exposing credentials or execution
  controls;
- added non-mutating structured-source probing with explicit diagnostics for unsupported ordinary
  websites, malformed URLs, recognized adapters, binding readiness, and secret-safe warnings;
- added trusted startup rebinding for persisted registries so process-local HTTP/MCP/SDK/framework
  authority can be reconstructed after restart without serializing credentials, live clients, or
  execution handles;
- versioned SQLite registry and trace storage formats, including validated transactional legacy
  v0 -> v1 metadata migration, inspection/migration CLI commands, safe backups, and fail-closed
  rejection of unknown future formats;
- added explicit accept/reject review for breaking schema drift, atomic high-level capability
  removal, unified runtime shutdown, and extensible adapter-plugin schema refresh lifecycles;
- expanded compatibility evidence with a live-provider protocol matrix plus installed-wheel
  validation against PydanticAI ToolSearch, OpenAI Agents SDK dynamic MCP filtering, and mcp-agent
  large-tool catalogs;
- added runnable real-provider quickstarts, protocol/framework demos, third-party adapter and
  decision-backend plugin examples, public trust evidence, contributor templates, and adoption
  instrumentation;
- added one-site English/Korean GitHub Pages with an in-header language selector, same-path fallback
  handling for untranslated pages, and source-blob translation drift checks.

### Changed

- made OpenAPI authentication requirements a typed, secret-free part of the canonical endpoint/tool
  fingerprint and schema-drift contract while leaving actual credentials in trusted runtime
  bindings;
- made automatic URL discovery passive by default and kept unsupported HTML/ordinary URLs
  fail-closed instead of guessing a tool contract;
- pinned schema watches, HTTP validators, refresh application, and trusted amendments to exact
  source/contract identity so remote drift cannot silently cross an accepted execution boundary;
- kept health probes coherent across accepted schema transitions and exposed detailed operational
  health/watch state through inspection/dashboard surfaces;
- broadened packaging acceptance to exercise external-style adapter plugins and major agent/tool
  ecosystem composition against the built wheel.

### Fixed

- preserved structured-source probe diagnostics instead of collapsing adapter-specific safe
  failures into ambiguous ingestion errors;
- replaced production runtime assertions with explicit fail-closed invariant checks where optimized
  Python execution could otherwise remove safety checks;
- hardened Research 0.14 GitHub Actions model-cache publication/recovery so long experiments can
  recover the same pinned model revision from cache eviction without changing frozen scientific
  corpora, prompts, scoring, thresholds, or model identities.

### Compatibility and migration

- no intentional breaking change is introduced to the 0.12 stable-core retrieval/execution facade;
- public OpenAPI endpoints with no authentication requirement preserve historical fingerprints;
  authentication changes now correctly produce security/breaking drift and require review/rebinding;
- legacy unversioned SQLite stores are supported as v0 and validated before transactional v1
  metadata migration; operators can use `schemarouter storage inspect` and
  `schemarouter storage migrate` with a backup before deployment;
- persisted registries still never store execution authority: use `bind_existing()` or
  `rehydrate_bindings()` to restore trusted process-local bindings after restart;
- active 0.14 retrieval/agent-utility research remains separate from stable package guarantees.

### Release integrity

- protected CI covers Python 3.10-3.14, Windows, minimum dependencies, typing, branch coverage,
  wheel/sdist clean-install acceptance, optional integrations, dependency auditing, CodeQL and
  Python preview;
- release automation publishes only from the exact green `main` SHA, creates the annotated tag,
  emits provenance attestations and an SPDX SBOM, publishes through PyPI OIDC, and verifies public
  artifact digests plus exact-version installs after publication;
- repository fact guards derive the stable version/date and experiment count from canonical sources,
  scheduled evidence export keeps the research record reproducible, and every new release emits
  `SHA256SUMS.txt` plus a machine-readable `release-manifest.json`.

## 0.13.0 - 2026-10-01

### Added

- expanded first-class capability ingestion beyond the 0.12 stable-core sources with GraphQL
  introspection, OData CSDL/`$select`, OpenRPC/JSON-RPC, declarative HTTP/JSON capabilities,
  inbound LangChain/LlamaIndex tools, explicit `ToolSpec` + trusted SDK/client binding, MCP
  stdio subprocesses, and transport-neutral MCP client factories;
- aligned structured output-field discovery across OpenAPI, MCP, OPTIMADE, Python callables and
  adapter plugins, including record-preserving nested array-item paths rather than flattening
  records out of their parent structure;
- added trusted local capability amendments for declaring missing result contracts without
  allowing imported execution identity or remote authority to be silently rewritten;
- added conservative one-shot provider schema refresh plus a periodic bounded-concurrency watcher
  with pending-review quarantine for breaking/security drift;
- added ETag/Last-Modified conditional refresh for safe single-document HTTP schema surfaces,
  preserving full-fetch correctness when validators are absent or insufficient.

### Changed

- broadened the documented universal-ingestion model around one typed Provider / Access path /
  Tool / Endpoint / Parameter / Field contract while keeping orchestration outside SchemaRouter;
- made registry replacement and invoker binding fail closed under concurrent schema changes through
  compare-and-swap registry updates and exact-fingerprint binding checks;
- kept unreleased source identity distinct from the published 0.12.0 artifact with the documented
  PEP 440 development-version lifecycle before this release was cut.

### Fixed

- completed the interaction between MCP stdio/custom transports and schema watching: URL-less MCP
  registrations now reinspect only through their current fingerprint-matched process-local trusted
  binding, never through fabricated source provenance;
- prevented malformed trusted contract amendments, stale refresh writes, HTTP-validator cache
  updates, and nested-array projection edge cases from weakening schema/binding drift boundaries;
- refreshed product documentation that still described implemented HTTP validators and array-item
  projection as future work.

### Compatibility

- no intentional breaking public API change is introduced relative to 0.12.0;
- the 0.12 stable-core retrieval/planning/execution authority boundary remains unchanged;
- all new protocol, SDK-binding, refresh/watch and field-contract surfaces are additive and keep
  credentials, live transports and execution authority outside model-visible schemas;
- active 0.14 retrieval/agent-utility experiments remain independent of this product release.

### Release integrity

- protected CI covers Python 3.10-3.14, Windows, minimum dependencies, typing, branch coverage,
  wheel/sdist clean-install acceptance, optional framework/MCP integrations, dependency auditing,
  CodeQL and Python preview;
- the automated release pipeline publishes only from the exact green `main` SHA, creates the
  matching annotated tag, emits provenance attestations and an SPDX SBOM, publishes through PyPI
  OIDC, and verifies public artifact digests and exact-version installs after publication.

## 0.12.0 - 2026-09-29

### Added

- published an explicit stable-core contract that freezes the current product architecture around
  typed capability registration/retrieval, downstream agent selection, validated invocation, and
  local execution-policy authority while allowing future research improvements behind that boundary;
- added public-facade regression coverage for `SchemaRouter` and `ConfiguredSchemaRouter`
  `retrieve` / `aretrieve` / executable-retrieval signatures and for the full
  `CapabilityCandidate` schema/fingerprint contract;
- added installed-package consumer acceptance for bounded retrieval, async retrieval, executable
  filtering, zero retrieval side effects, full input/output schema preservation, fingerprints, and
  the subsequent separation between retrieval and actual invocation;
- added LangChain and LlamaIndex regression tests proving framework adapters cannot bypass
  SchemaRouter mutation policy.

### Changed

- formally closed the current product-development cycle as a pre-1.0 stable-core boundary:
  performance/research work may change compatible retrieval indexes, ranking backends, shortlist
  policies, adaptive depth, corrective re-retrieval, and defaults without redefining the public
  execution-authority boundary;
- repaired the framework-maturity documentation table and added the stable-core contract to the
  public documentation navigation;
- refreshed CodeQL action pins to v4.38.2 and aligned release-metadata expectations;
- retained ongoing B2/held-out/final-answer research as independent evidence tracks rather than
  package-release blockers unless they expose a reproducible correctness, security, policy,
  execution-authority, API-integrity, or packaging defect.

### Compatibility

- no intentional breaking change is introduced relative to 0.11.0;
- the Top-K typed retrieval APIs shipped in 0.11.0 remain the frozen public retrieval facade for the
  current research cycles;
- existing planning, invocation, async, batch, streaming, policy, validation, inspection, tracing,
  persistence, and optional framework integration surfaces remain available;
- SchemaRouter remains Beta / pre-1.0: future 0.x minors may still make explicit, documented
  compatibility changes, but benchmark improvements alone are no longer sufficient justification
  to redesign the core facade.

### Release integrity

- protected CI validates Python 3.10-3.14, Windows smoke, minimum dependencies, typing, branch
  coverage, docs, packaging, optional integrations, security auditing, and CodeQL;
- wheel and sdist clean-install acceptance exercises the released retrieval surface;
- the automated release pipeline builds from the exact green main SHA, creates the annotated tag,
  emits provenance attestations and an SPDX SBOM, publishes through PyPI OIDC, and verifies public
  wheel/sdist digests and exact-version installs after publication.

## 0.11.0 - 2026-09-29

### Added

- added first-class bounded Top-K typed capability retrieval through `SchemaPlanner.retrieve/aretrieve`
  and `SchemaRouter.retrieve/aretrieve`, returning registered `CapabilityCandidate` bundles without
  planning, execution, or side effects;
- added `retrieve_executable/aretrieve_executable` for applications that need the same compact
  candidate surface restricted to routes with current local execution binding readiness;
- retrieval candidates preserve the full effective input/output JSON Schemas together with
  registered parameter/output contracts, semantic IDs, datatypes, optional units/normalization/
  qualifiers, provider/access identity, read/write/destructive metadata, and schema fingerprints;
- added deterministic public-contract tests for Top-K ordering, K validation, async analyzers,
  cooldown/unavailability filtering, binding readiness, detached result snapshots, and zero execution
  side effects.

### Changed

- aligned the public product model with the 0.14 research framing: SchemaRouter is a typed capability
  retrieval and validated execution boundary for surrounding RAG/agent systems, not a general agent
  framework or autonomous final tool selector;
- separated stable package release gates from ongoing B1/B2, answer-quality, adaptive-depth,
  corrective-retrieval, held-out-generalization, and representation-ablation research;
- refreshed research/status documentation while retaining prior negative results and research
  governance as evidence rather than product blockers.

### Compatibility

- the new retrieval APIs are additive; existing `plan`, `plan_executable`, `invoke`, async,
  batch, streaming, validation, policy, and execution behavior are unchanged;
- retrieval never grants execution authority and never invents unregistered tools or fields;
- SchemaRouter remains Beta / pre-1.0 so future 0.x minors may contain deliberate documented public
  API refinements.


## 0.10.0 - 2026-09-28

### Added

- clarified SchemaRouter's product model as typed capability retrieval/execution infrastructure: APIs and tools are parsed into registered endpoint/field contracts and searched like an executable analog of RAG indexing, while orchestration remains outside the package;
- documented JSON datatype/shape, semantic IDs, optional source units, explicit canonical unit normalization, and exact qualifiers as first-class capability/data-contract metadata rather than model-inferred semantics;
- published a public routing-research status page that separates development evidence, independent fresh confirmation, conservative reference profiles, and successor research prototypes;
- added a frozen routing runtime-parity validator that rejects route changes, execute/abstain threshold crossings, case-set drift, execution errors, or authority violations while reporting probability drift for runtime-only optimization evidence;
- added a machine-validated operation-routing freeze protocol that records immutable source/model/runtime/representation/rule provenance, DEV and independent fresh-confirmation artifact evidence, standing 85/97/100/1 quality gates, authority invariants, and the #197 → #198 handoff before calibration/blind evaluation.
- added explicit third-party bounded decision-backend entry points through the `schemarouter.decision_backends` package metadata group; discovery is metadata-only, loading is explicit by exact name, duplicate names fail before import, returned options remain locally bounded, and shared benchmark reports record only non-secret plugin metadata/config keys.
- generalized Jev-compatible decision providers behind `SystemOneDecisionBackend`, preserving `JevDecisionBackend` while allowing compatible hosted/self-hosted runtimes to swap `base_url`, model, and provider label without changing planner semantics.
- generalized the decision-routing benchmark for arbitrary System One-compatible providers and bounded Python decision callables so new typed-decision models can be evaluated without adding model-specific planner code.
- closed the 0.10 cheap-first MiniLM→BGE cascade study after the frozen `r030-a060-m005` candidate reproduced a 14.983% same-runner mean-latency reduction (504.541 ms → 428.946 ms) but missed the preregistered 95% near-domain unsupported-operation rejection floor at 94.792% (91/96); the candidate was rejected without calibration retuning, the unused v14 blind-final reservation was retired without generation, and the consumed research workflows were removed.
- consumed the post-freeze v13 blind-final corpus exactly once with sibling-contrastive BGE (beta=1.0): 75.0% overall accuracy, 61.719% supported-operation routed accuracy, 98.438% near-domain unsupported-operation rejection, 100% OOD rejection, and 75.869% supported/rejection harmonic mean with zero invalid plans or execution errors; v13 is now permanently ineligible for tuning.
- reserved a 600-case multilingual v12 contrastive operation stress set, then explicitly classified it as design-known rather than blind evidence because its exact construction was inspected before architecture selection; v12 remains ineligible for tuning. A separate v13 protocol now requires the next fresh corpus to be generated only after the candidate is frozen and scored in the same one-shot run without intermediate inspection.
- selected sibling-contrastive BGE with `beta=1.0` on v5 development data only, then confirmed the unchanged candidate on the v5 calibration split at 80.208% overall accuracy, 62.5% supported-operation routed accuracy, and 97.917% near-domain unsupported-operation rejection; the complete candidate is frozen before any v13 blind-final generation.

### Changed

- consolidated the stable default around field-first deterministic planning, typed registry contracts, bounded optional decision backends, fail-closed policy/schema validation, provider/access health, and conservative fallback;
- kept experimental open-set capability verifiers and model-specific research paths outside the unconditional production default until they pass preregistered generalization and fresh-confirmation gates;
- formally closed the 0.11 operation-routing architecture-search cycle without a promoted production-target candidate after its strongest canonical DEV pass failed exact frozen zero-overlap fresh confirmation.
- evaluated the first registry-compiled arbitrary-tool capability verifier on canonical DEV and a separate unseen native/OpenAPI/MCP registration holdout; the typed compiler preserved authority and data contracts, but the synthetic learned veto retained only 5.69% / 2.46% of raw-correct winners and was terminally rejected without label-driven repair.

## 0.9.0 - 2026-09-26

### Added

- added a provider-neutral bounded `PairwiseDecisionBackend` for application-owned cross-encoders/rerankers; pair scores are mapped only to already-authorized opaque option IDs, metadata is not forwarded by default, malformed/out-of-range scores fail closed, and no model/runtime dependency is added to core.
- consumed the previously reserved 600-case multilingual v11 operation-generalization holdout exactly once with the frozen BGE pairwise candidate, then ran the pre-existing MiniLM 0.40 baseline only as a post-holdout diagnostic on the same consumed corpus. The BGE candidate improved the pre-registered balanced operation objective from 59.115% to 61.589% (+2.474 pp) by raising near-domain unsupported-operation rejection from 77.604% to 97.396%, while supported-operation routed accuracy fell from 40.625% to 25.781%; BGE is therefore not promoted to an unconditional default.

### Changed

- benchmark reporting now records pairwise operation-fit callable and score-threshold configuration explicitly, so consumed holdout evidence preserves the scoring path used for evaluation.

## 0.8.0 - 2026-09-26

### Added

- froze a new 600-case multilingual v10 operation-generalization holdout before post-v9 routing-surface optimization; after selecting a concise operation-fit representation and retaining the 0.40 threshold from v5 development/calibration only, consumed v10 exactly once at 55.667% overall accuracy, 42.188% supported-operation routed accuracy, 77.083% near-domain unsupported-operation rejection, and 100% ordinary out-of-domain rejection; v10 is now consumed regression evidence and is not eligible for retuning;
- reserved a fresh 600-case multilingual v9 alias-aware operation holdout after detecting that v8 had been accidentally consumed by a calibration diagnostic path; corrected calibration to use consumed v7 only and kept v9 manual/threshold-gated;
- froze the alias-aware operation-fit threshold at 0.40 from v5 development/calibration only and consumed v9 exactly once: 51.167% overall accuracy, 38.281% supported-operation routed accuracy, 70.833% near-domain unsupported-operation rejection, and 100% ordinary out-of-domain rejection; v9 is now regression evidence and is not eligible for retuning;
- explicit trusted `EndpointSpec.operation_aliases` vocabulary for bounded operation-fit, with validation, fingerprinting, compatible schema-diff reporting, inspection/dashboard visibility, and no automatic/model-authored alias inference;
- optional bounded `operation_fit_backend` gate for single-call plans that checks only sibling
  endpoint operations inside the currently leading tool domain, deliberately excluding broad tool
  descriptions, tool-name labels, and output-field labels; the gate can suppress unsupported operations but cannot add,
  select, reorder, or switch execution candidates;
- separate multilingual v5 operation calibration (576 cases) and v6 operation regression holdout
  (600 cases) corpora for measuring near-domain unsupported-operation rejection without reusing the
  already-consumed v4 holdout; v6 was consumed before the tool-domain-label cleanup and is retained
  as regression evidence rather than reused for a new untouched claim;
- a separate 600-case multilingual v7 post-change operation holdout, reserved before measuring the tool-domain-label-cleaned operation-fit surface so v6 can remain regression evidence rather than be reused for a new untouched claim;
- recorded the consumed v7 result as distribution-shift evidence and restored the holdout workflow to its manual, explicit-threshold guard after the one-shot run;
- reserved a fresh 600-case multilingual v8 operation-alias holdout before implementing trusted endpoint operation aliases;
- optional bounded `endpoint_disambiguation_backend` stage that may reorder only sibling endpoints
  inside the currently leading tool domain for single-call plans, preserving the existing candidate
  order on backend failure/abstention and never switching tools or creating execution authority;
- optional bounded `candidate_fit_backend` gate after lexical/semantic candidate recall, allowing
  explicit no-route abstention without selecting the final route or creating execution authority;
  backend failures retain the already-authorized candidates and live inspection/dashboard expose the
  configured fit backend;
- a reproducible 600-case multilingual v3 untouched holdout for capability-fit evaluation, kept
  separate from the already-consumed v2 test split and checked for normalized exact-query overlap;
- optional bounded semantic candidate recall through a separate `candidate_recall_backend` and
  `candidate_recall_limit`, allowing lexical candidates to be unioned with multilingual semantic
  top-k recall before the existing final bounded decision/policy/execution path; live inspection and
  dashboard output expose the recall backend and bound;
- a reproducible 1,200-case decision-routing v2 stress corpus with six language groups, balanced
  per-route coverage, explicit no-route cases, fixed dev/calibration/test splits, exact generator
  reproducibility tests, and benchmark split/language metrics;
- runtime evidence revalidation with separate `ToolCall.required_evidence` and route-available
  `ToolCall.evidence`, shared planner/executor evidence checks, fail-closed rejection of forged
  evidence overclaims, unmet global/per-field requirements, unselected field requirements, and
  conflicting source-type contracts;
- trusted semantic `PlanRequest.field_evidence` constraints so heterogeneous requests can require
  units, provenance, license, or source type for one logical field without imposing that requirement
  on unrelated unitless/text fields; compiled calls expose the matched local field requirements and
  model-assisted analysis cannot author or broaden them;
- structured `ExecutionPlan.coverage` reporting with required, covered, and uncovered semantic-field
  requirements plus an explicit completeness flag and warning when bounded planning cannot satisfy the
  full matched field set;
- multi-call decision/backend separation so model-assisted candidate selection prioritizes candidates
  without pruning the deterministic schema-recalled pool before complementary field-coverage
  selection; single-call and empty-recall fail-closed behavior remain unchanged;
- coverage-aware selection for explicit multi-call plans so bounded call slots prefer complementary semantic fields across heterogeneous providers/access paths instead of redundant routes for an already-covered field, stop early once matched field coverage is complete, and keep exact query-visible qualifiers as distinct coverage requirements;
- explicit multi-provider corroboration and aggregation contracts with `PlanRequest.retrieval_mode="corroborate"`, strict trusted-identifier canonical identity, provenance-preserving `SourceRecord` / `FieldObservation` / `CanonicalEntity` models, and scientific observation preservation instead of silently collapsing conflicting values;
- a dedicated design-principles document clarifying field-first semantics, provider/access separation, general optional-unit contracts, access-path health, multi-source field unions, bounded model authority, and fail-closed equivalence.

### Changed

- simplified the bounded operation-fit embedding surface to the endpoint operation name, trusted operation aliases, and endpoint description while removing generic operation-class / HTTP-method boilerplate; a v5 dev/cal representation comparison selected this concise surface, and a 0.05–0.70 v5-only sweep retained `operation_fit_min_similarity = 0.40` with a 69.792% balanced supported/near-domain score on both development and calibration;
- global provenance evidence now applies consistently to the entire selected answer surface: a
  tool-level source type covers the route, otherwise every selected answer field must declare source
  provenance; active unknown `field_evidence` semantic IDs now fail closed during planning instead of
  being silently ignored;
- promoted the 0.8 development line to the non-prerelease `0.8.0` release after the bounded semantic-routing, multi-provider evidence, reproducibility, packaging, and security gates passed.

## 0.7.0 - 2026-09-25

### Added

- optional exact `FieldSpec.qualifiers` for scientific measurement/material context such as
  temperature, phase, orientation, or method; qualifiers participate in fingerprinting, exact
  cross-provider fallback compatibility, qualifier-aware deterministic ranking and bounded field
  selection, ToolResult field contracts, inspection/dashboard views, model analyzer semantic
  catalogs, and schema-diff drift classification;
- trusted `ParameterSpec.aliases` routing that copies argument values unchanged across provider-specific
  local parameter names, with exact-name precedence, ambiguity fail-closed behavior, candidate-index
  support, and independent fallback compilation per access contract;
- conservative schema-drift analysis for trusted `EndpointSpec` / `ToolSpec` snapshots, including
  additive/breaking/security-review classification, security-sensitive HTTP method and side-effect
  changes, and `schemarouter inspect diff` for persisted SQLite registries; compatibility reports
  remain diagnostic and never bypass exact fingerprint rejection;
- ordered operation-scoped `PolicyRule` controls with explicit `allow`, `deny`, and
  `require_approval` effects plus remote/read-only/destructive/unclassified predicates, while the
  existing category-level policy remains the fallback when no rule matches;
- structured `PlanExplanation` output with deterministic score components, projected-field
  retention reasons, ignored undeclared argument names, and bounded decision-selection source,
  without exposing model chain-of-thought;
- explicit `parallel_read_only` in-plan fan-out with full preflight schema/binding/policy checks,
  completion-order streaming/events, one shared execution budget, and an independent
  `max_parallel_calls` bound so batch concurrency does not multiply implicitly;
- opt-in provider-aware read-only fallback routes with explicit `provider` / `access_mode`
  identities, same-provider-before-cross-provider ordering, per-alternative schema/evidence
  compilation, semantic field-alias compatibility checks, explicit `InvocationUnavailableError`
  triggers, and typed `tool.fallback` observability;
- explicit `ServerProjectionSpec` contracts that push planned logical fields into upstream
  selectors such as OpenAPI `fields=...` and OPTIMADE `response_fields=...`, while preserving
  raw-response validation and final local projection;
- conservative nested-object projected-schema validation for trusted server-side field projection,
  including root arrays of objects; selected paths that require unsupported array traversal,
  refs/unions, or otherwise unprovable shapes retain the full schema and fail closed;
- bounded passive access-path cooldown plus optional trusted `AccessHealthMonitor` probes that
  reopen recovered read-only routes without permanent blacklisting or model-controlled health state;
- field-first execution documentation that formalizes query -> required logical fields ->
  provider/access selection -> upstream projection -> validated minimal `ToolResult` as a core
  architectural principle;
- typed scientific field contracts with conservative JSON value-shape fallback compatibility,
  case-sensitive source units, explicit affine `UnitNormalizationSpec` conversion into canonical
  units, numeric-array support, and compact `ToolResult.field_contracts` metadata;
- strict scientific contract validation that enforces selected `FieldSpec.json_schema` values at
  runtime, requires explicit datatypes for unit-bearing automatic fallback, rejects contradictory
  field/raw type declarations, and compares post-normalization canonical result datatypes;
- OpenAPI/MCP preservation of recognized source-unit schema annotations plus typed field-contract
  inspection/dashboard views showing result type, source/canonical units, physical dimension,
  normalization state, and provider/canonical projection paths without inferring conversions;

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
- published extras compatibility smokes that verify MCP/Jev/OpenTelemetry in an isolated
  environment and separately resolve the combined
  MCP/LangChain/LangGraph/LlamaIndex/Jev/OpenTelemetry extras from PyPI, preventing framework
  transitive dependencies from masking lightweight-extra packaging regressions while still testing
  full co-installation;
- exact-version post-publish release verification that re-installs the newly published PyPI wheel,
  forced sdist, isolated MCP/Jev/OpenTelemetry extras, and the combined
  MCP/LangChain/LangGraph/LlamaIndex/Jev/OpenTelemetry extras after publication, with bounded
  index-propagation retries and public-surface execution outside the checkout;

### Changed

- explicit `EvidenceRequirements` are now deterministic local planning constraints even when no
  model-backed evidence judge is enabled: missing requested units/provenance/license/source-type
  evidence removes that candidate locally, while an enabled decision backend may only veto already
  sufficient local evidence and cannot upgrade missing evidence;
- execution-facing router APIs now plan across access paths that are both health-eligible and
  currently bound to the same tool fingerprint, while `plan()` / `aplan()` remain schema-planning
  surfaces and explicit `execute(plan)` never replans; `plan_executable()` /
  `aplan_executable()` expose the live execution-ready planning surface directly;
- live inspection/dashboard execution state now distinguishes `ready`, `unbound`, `stale`, and
  `orphaned` invoker bindings from remote/local access-health cooldown state;
- split descriptive `metadata` from fingerprinted execution-contract metadata: built-in adapters
  now place transport/runtime semantics in `ToolSpec.execution_metadata` /
  `EndpointSpec.execution_metadata`, while `ToolSpec.remote` is the fingerprinted execution-origin
  classification. Legacy built-in registry JSON is migrated on validation;
- planner-generated calls and LangChain/LlamaIndex bridges now include `tool_fingerprint` in
  addition to endpoint fingerprints. Manually constructed remote or runtime-sensitive `ToolCall`
  values must provide the current tool fingerprint; replan/recreate the call instead of reusing an
  older serialized call;

- raised the blocking branch-coverage floor from 82% to 84%;
- made the protected `package` CI check depend on both the Laya integration contract and a
  dependency vulnerability audit, so either regression blocks merge even when the repository
  ruleset predates newer job names;
- package smoke now verifies benchmark JSON and HTML artifact generation;
- package validation now executes consumer acceptance scenarios from clean wheel and sdist
  environments, verifies MCP/Jev/OpenTelemetry from an isolated built-wheel environment, separately
  resolves the combined MCP/LangChain/LangGraph/LlamaIndex/Jev/OpenTelemetry extras, runs
  no-network SDK smoke checks, executes each framework example, and exercises the installed
  inspection/dashboard CLI against real persisted registry/trace artifacts;
- current-source public OpenAPI/OPTIMADE compatibility jobs now use non-editable installation plus
  `pip check` before live service calls, reducing the gap between source CI and downstream package
  behavior;
- research benchmarking now compares Laya's lexical-only path with explicit empty-candidate recall
  on the same full corpus and hardware;
- promoted the 0.7 development line to the non-prerelease `0.7.0` release after the field-first routing, fallback/health, scientific-contract, policy, observability, packaging, and supply-chain gates passed.

### Security

- scientific fallback now rejects known datatype mismatches, missing/asymmetric unit contracts,
  incompatible physical dimensions/canonical units, non-numeric unit-bearing fields, and
  non-finite/overflowing unit normalization results;
- unit contracts reject empty/whitespace-padded symbols, non-identity transforms when source and
  canonical unit labels are identical, and contradictory affine transforms for the same source unit
  across fallback routes;
- optional read-only fallback routes that are removed, schema-drifted, policy-invalid, unbound, or
  stale-bound are pruned before invocation instead of blocking a still-valid primary, while primary
  schema/policy violations and currently valid mutating fallback contracts remain fail-closed;
- hardened stale-plan authority boundaries so local/remote classification, approved transport
  origin, and built-in runtime adapter semantics cannot change through unfingerprinted descriptive
  metadata or survive a rebind under an old plan;
- automatic fallback never treats schema, policy, approval, stale-state, deterministic 4xx, or
  mutation failures as availability signals; complete fallback chains are preflighted and only
  explicitly read-only candidates can participate;
- operational inspection now derives execution-critical provenance from the fingerprinted contract
  rather than ordinary metadata mirrors, preventing observability from reporting spoofed authority
  state; URL userinfo/query/fragment values are stripped from inspection/dashboard output, and
  schema/document provenance is sanitized before it reaches model payloads or persisted tool state;

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
  attest that SBOM against wheel/sdist artifacts, and attach the SBOM to the GitHub release;
- post-publish release verification now downloads the exact wheel and sdist from public PyPI and
  requires their SHA-256 digests to match the trusted build artifacts before accepting the release.

### Compatibility

- no intentional public API removals are introduced relative to `0.6.0`;
- new fallback, health, policy, scientific-field, qualifier, parameter-alias, schema-diff, parallel-read, and planning-explanation surfaces are additive, with behavior-changing paths remaining explicit or fail-closed;
- scientific datatype/unit/qualifier compatibility is stricter for automatic fallback, so ambiguous or under-specified cross-provider substitutions that cannot be proven safe are rejected rather than guessed;
- the project remains pre-1.0, so later 0.x minor releases may still include deliberate documented compatibility changes.

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

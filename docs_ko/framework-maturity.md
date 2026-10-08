# Framework 성숙도 매트릭스

SchemaRouter는 의도적으로 LangChain보다 좁은 범위를 다룹니다. 목표는 범용 agent framework를 재현하는 것이 아니라 schema-aware tool planning과 execution을 production-grade로 만들고 더 큰 ecosystem에 쉽게 내장할 수 있게 하는 것입니다.

이 문서는 research metric이 아니라 framework-level maturity를 추적합니다.

> **0.17.0 maturity note:** stable core는 이제 provider-first capability registration, governed execution, host-verified authorization/data scope, schema-introspected data-system onboarding, bounded decision backend, versioned snapshot/artifact, privacy-safe decision trace를 포함합니다. Retrieval은 여전히 registered capability contract를 반환할 뿐 execution authority를 부여하지 않습니다. Research evidence는 stable product guarantee와 분리됩니다. [Research status](research/routing-status.md)를 참고하십시오.

| Capability | 현재 main | 방향 |
| --- | --- | --- |
| Typed tool / endpoint / parameter / field contract | 구현됨 | Core invariant |
| Capability retrieval | Registered route에 대한 first-class deterministic `retrieve` / `aretrieve` + executable-ready variant | 명시적 contract와 evidence 뒤에서만 alternate index/representation 추가 |
| Provider-first onboarding | 명시적 method/credential/dependency status를 가진 built-in/local/plugin `ProviderProfile` registry; Materials Project, Crossref, Tavily acceptance coverage | Planner에 provider branch를 추가하지 않고 provider catalog 확장 |
| State-aware capability retrieval | 동일 visible surface에서 명시적 fixed-Top-K filtering + 별도 eligible-Top-K corrective backfill | Host state를 명시적으로 유지하고 orchestration authority는 core 밖에 유지 |
| Capability dependency graph | Semantic-indexed construction, incremental rebuild, deterministic SCC, bounded cycle witness, sparse 1k/10k/50k benchmark | 실제 registry scale이 요구할 때만 distributed storage 추가 |
| Capability snapshot / artifact | Content-addressed snapshot, atomic CAS publication, versioned portable artifact/snapshot document, deterministic legacy migration | Host-owned infrastructure 뒤에서만 external artifact store/signing 추가 |
| Unified decision trace | CLI/dashboard inspection을 포함한 retrieval/eligibility/state/health/drift/policy/constraint/negotiation/fallback/lineage result의 privacy-safe aggregation | Hidden inventory 또는 payload leakage 없이 trusted export sink 추가 |
| Natural-language planning | Deterministic scoring + registry version별 cached exact-recall candidate index | Planning/execution authority를 external agent selection과 분리 유지 |
| Sync / async invocation | 구현됨 | 안정적인 public surface |
| Batch execution | completion-order API를 포함해 구현됨 | 안정적인 public surface |
| Result streaming | 기본 sequential + 명시적 read-only parallel completion streaming | Dependency/DAG semantic을 core 밖에 유지 |
| Typed event streaming | 구현됨 | Payload를 노출하지 않고 exporter ecosystem 확장 |
| Input / output / config schema introspection | 구현됨 | Machine-readable 상태 유지 |
| Retry policy | Read-only gate + 명시적 non-retryable invocation marker + built-in OpenAPI/OPTIMADE HTTP classification | Recovery semantic이 명확한 경우에만 protocol-specific classifier 확장 |
| Python callable tool | 구현됨 | Docstring parameter description 개선 |
| Structured-source adapter registry | 명시적 entry-point plugin으로 구현됨 | Certified third-party adapter 확장 |
| OpenAPI ingestion | Common subset + operation-over-path parameter overrides + default path/query/header serialization + flattened object bodies + generic typed JSON root bodies + discriminator-aware tagged oneOf bodies + schema-less body reporting + spec-ignored header filtering + collision-safe generated operation names + multi-2xx JSON/no-content response validation + local refs + opt-in bounded same-origin cross-document refs + static same-origin $id/$anchor resolution + OpenAPI 3.0 nullable normalization + allOf object flattening + oneOf/anyOf response-field discovery + compatibility report | Keep dynamic refs, non-default parameter styles, and automatic variant selection fail-closed; expand only behind typed contracts |
| OPTIMADE ingestion 및 execution | v0.2에서 구현됨 | Provider federation / index meta-database traversal 추가 |
| MCP ingestion 및 execution | Streamable HTTP, trusted stdio subprocess, caller-owned transport-neutral client factory로 구현됨 | OAuth/gateway example 확장 |
| GraphQL / OData / OpenRPC ingestion | Native selection/projection 또는 RPC semantic으로 현재 main에 구현됨 | Protocol semantic이 deterministic한 경우에만 확장 |
| 사람이 읽는 API documentation | Grounded proposal flow | Multi-page/browser discovery 추가 |
| Runtime policy | Category default + ordered operation-scoped allow/deny/approval rule + execution budget | Trusted local boundary 뒤에서만 external organization policy adapter 추가 |
| Runtime JSON Schema validation / projection | Full raw validation + 명시적 nested object projection path + trusted server-side field selector | 필요한 경우에만 typed array-element projection 추가 |
| Schema drift analysis | Conservative endpoint/tool compatibility report; exact fingerprint가 계속 execution을 gate | Drift rejection을 약화하지 않고 CI/reporting integration 추가 |
| Planning explanation | Structured score component, field-selection reason, ignored-argument record, decision-selection source | Explanation을 structural하게 유지하고 model chain-of-thought는 노출하지 않음 |
| In-plan concurrency | Preflight validation, completion streaming, shared budget을 갖는 명시적 flat `parallel_read_only` fan-out | DAG/dependency/write orchestration을 core 밖에 유지 |
| Provider/access fallback | Semantic field compatibility와 typed fallback event를 갖는 precompiled read-only same-provider/cross-provider route | 명시적 contract를 통해서만 provider federation 확장 |
| Multi-provider corroboration / aggregation | Explicit cross-provider corroboration + strict trusted-identifier identity resolution + provenance-preserving scientific observation | Fuzzy identity와 truth adjudication은 core 밖에 유지 |
| Scientific field contract | Explicit JSON value shape, optional exact unit, affine canonical normalization, exact trusted qualifier, qualifier-aware routing, fail-closed fallback compatibility | Ontology/unit inference는 core 밖에 유지하고 richer scientific semantic은 explicit trusted contract로만 추가 |
| Provider parameter alias | Trusted exact/alias binding + ambiguity fail-closed + independent fallback compilation | Model-generated parameter remapping은 execution boundary 밖에 유지 |
| Access health | 유한 passive cooldown + early reopen을 지원하는 optional trusted background probe | Model authority 없이 external health source 통합 |
| LangChain / LangGraph / LlamaIndex integration | Optional adapter와 native graph node 구현됨 | Ecosystem listing 확장 |
| Bounded decision backends | Semantic candidate recall, broad capability-fit, operation-fit, same-tool endpoint disambiguation, candidate/field selection, and conservative evidence-sufficiency surfaces; provider-neutral callable/embedding + optional Jev/Laya/Ollama, all opt-in | Gather live decision evidence and keep model authority bounded |
| Jev / TypeSafe decision provider | Optional adapter 구현됨 | Quality gain을 주장하기 전에 live workload evidence 수집 |
| Local Laya decision provider | Auto language routing, confidence abstention, lazy/preloaded checkpoint, shared benchmark support를 갖는 optional local choice adapter | Default 선택 전에 checkpoint/hardware-specific evidence 수집 |
| Local Ollama decision provider | Structured-output HTTP API 기반 구현됨 | Quality claim 전에 특정 local model/hardware benchmark |
| Decision benchmark harness | Versioned multilingual stress/calibration/fresh-confirmation corpora, machine-readable freeze/terminal evidence, JSON/CSV/HTML reporting, and an explicit 85/97/100/1 + 250 ms standing target; latest closed cycle has no promoted target candidate | Continue only with preregistered materially new capability evidence and independent fresh confirmation |
| Framework callback / exporter | Typed redacted event + optional OpenTelemetry exporter | 필요에 따라 additional trusted sink 추가 |
| Middleware interception | Detached snapshot을 사용하는 trusted ordered before/after execution hook | 필요한 경우에만 organization-specific hook library 추가 |
| Composition / DAG runtime | Core 범위 밖 | 중복 구현 대신 LangGraph와 통합 |
| Replayable run trace persistence | SQLite append-only event trace + non-executing replay | 필요에 따라 alternate trusted store/export path 추가 |
| Persistence / checkpoint | Workflow checkpoint는 범위 밖 | Orchestration state를 LangGraph 또는 다른 runtime에 위임 |
| HTTP serving layer | 미구현 | Optional server package 검토 |
| Pluggable registry boundary | `ToolRegistry` protocol + transactional `SQLiteRegistry` | 필요한 경우에만 distributed/remote implementation 추가 |
| Release / compatibility policy | 구현됨 | RC review에서 강제 |
| Package artifact CI | Implemented with clean wheel/sdist smoke, public-surface consumer acceptance scenarios, built-wheel optional-extra resolution/import smoke, framework-example execution, provenance, and SPDX SBOM attestations | Keep artifact verification blocking |
| Security automation | Weekly/PR dependency audit + push/PR/scheduled CodeQL + OpenSSF Scorecard + immutable Action pin | Fail-closed runtime policy를 약화하지 않고 finding triage |
| Documentation site | MkDocs Material로 구현됨 | Strict docs build를 blocking으로 유지 |
| Integration certification suite | Baseline 구현 + machine-readable OpenAPI/OPTIMADE smoke artifact 보존 | Live compatibility matrix 확장 |

## 성숙한 framework에서 SchemaRouter가 가져와야 할 점

### 1. 하나의 실행 vocabulary

모든 주요 component가 동일한 execution verb를 따르면 framework를 더 쉽게 학습할 수 있습니다.
따라서 SchemaRouter는 다음을 제공합니다:

- `invoke` / `ainvoke`
- `batch` / `abatch`
- `stream` / `astream`
- `astream_events`
- `with_config`

이 method들은 planner, policy, schema validation, binding-drift check를 우회하지 않습니다.

### 2. 공개 contract로서의 introspection

`input_schema`, `output_schema`, `config_schema`는 public machine-readable interface입니다.
이 interface들은 serving layer, UI generation, testing, framework integration을 위한 것입니다.

### 3. Tool 작성 비용은 낮아야 함

Python callables can be registered directly through `add_callable()` and optionally annotated with
`@schema_tool`. Explicit ToolSpec + trusted invoker binding covers opaque SDKs. OpenAPI, OPTIMADE,
MCP, GraphQL, OData, and OpenRPC are built-in structured paths, while `AdapterRegistry` keeps
additional protocol logic out of the core planner. Existing LangChain/LlamaIndex tools can also be
imported into the canonical capability model.

### 4. Integration은 선택적이어야 함

Core package가 dependency aggregator가 되어서는 안 됩니다. Ecosystem bridge와 decision provider는 optional extra와 lazy import 뒤에 두어야 합니다.

### 5. Observability가 privacy를 약화해서는 안 됨

Event payload는 기본적으로 redaction됩니다. Argument와 result payload는 `RunConfig(include_payloads=True)`를 명시적으로 선택한 경우에만 나타납니다.

## SchemaRouter가 따라 하지 말아야 할 점

- general chat/message abstraction;
- prompt template ecosystem;
- schema planning과 무관한 model-provider wrapper;
- memory/checkpoint system;
- 두 번째 graph runtime;
- schema contract를 약화하는 hidden coercion.

이러한 concern은 surrounding framework가 처리하는 편이 낫습니다. SchemaRouter는 tool schema를 위한 집중된 compiler/runtime boundary로 남아야 합니다.

## 다음 성숙도 gate

### Gate A — 공개된 non-prerelease baseline

Package, documentation, release automation, deterministic compatibility test, public OpenAPI/OPTIMADE smoke가 마련되어 있습니다.

### Gate B — ecosystem-ready

로컬에서 완료된 항목:

- 실행 가능한 LangChain, LangGraph, LlamaIndex example;
- 공개된 ecosystem compatibility 및 maintenance policy;
- adversarial contract test를 갖는 optional Jev decision provider;
- bounded choice validation과 shared benchmark support를 갖는 optional local Laya decision provider;
- provider-neutral embedding-similarity decision backend with threshold/margin abstention and
  malformed-vector fail-closed validation;
- provider-neutral pairwise query-option decision backend for application-owned rerankers, with
  bounded score validation and no model/runtime dependency in core;
- identifier preservation과 deterministic fallback을 갖는 bounded field-selection contract;
- conservative evidence-sufficiency contract with local provenance/license/unit/source-type precheck
  and provider veto-only semantics;
- provider-neutral decision benchmark harness;
- live Materials Project/Crossref acceptance와 explicit Tavily auth handling을 갖는 provider-first registration profile;
- stable stateless retrieval facade를 보존하는 explicit state-conditioned re-retrieval;
- bounded SCC cycle analysis를 갖는 indexed/incremental capability dependency graph;
- atomic capability snapshot publication + versioned artifact/snapshot migration 및 integrity check;
- inspection, CLI, dashboard와 통합된 unified privacy-safe capability decision trace;
- registry-version cache invalidation과 exhaustive parity test를 갖는 exact-recall candidate index;
- 1,200-case multilingual/adversarial v2 benchmark corpus plus separate frozen calibration/holdout corpora for capability-fit, endpoint disambiguation, and operation-fit evaluation;
- OpenAPI compatibility reporting;
- opt-in bounded same-origin cross-document OpenAPI reference bundling;
- authenticated MCP transport boundary;
- per-call approval 및 per-run execution budget;
- explicit allow/deny/approval effect를 갖는 operation-scoped local policy rule;
- fingerprint check를 절대 우회하지 않는 conservative endpoint/tool schema diff report;
- deterministic/runtime-visible signal에서 도출된 structured planning explanation;
- preflight validation과 shared run budget을 갖는 flat read-only parallel fan-out;
- field-first server-side projection contract + final local projection;
- finite cooldown과 trusted health-probe recovery를 갖는 bounded provider/access fallback;
- privacy-preserving OpenTelemetry exporter;
- 명시적으로 allowlist된 third-party adapter plugin;
- property-based OpenAPI default-serialization coverage;
- self-contained decision benchmark HTML reporting and multi-run history rendering;
- retained machine-readable public OpenAPI/OPTIMADE compatibility smoke artifacts;
- public-surface consumer acceptance validation across supported Python versions, Windows,
  minimum dependencies, wheel, and sdist installs, with built-wheel MCP/Jev/OpenTelemetry
  import/initialization smoke plus LangChain/LangGraph/LlamaIndex runnable examples.

아직 external 또는 follow-up 작업:

- upstream ecosystem listing/discussion requests;
- broader live hosted-provider benchmark evidence; local/open routing evidence includes consumed
  v10 MiniLM and v11 pairwise-BGE generalization holdouts;
- dynamic OpenAPI/JSON-Schema reference semantics and automatic planner-side schema-variant selection.

### Gate C — production 운영

로컬 구현 완료:

- deterministic call/attempt/remote/time/cost budget;
- trusted sync/async per-call approval;
- redacted event stream의 OpenTelemetry span export;
- authenticated MCP/custom client-factory boundary;
- 명시적으로 allowlist된 adapter plugin loading;
- transactional persistent SQLite registry behind the `ToolRegistry` protocol;
- OpenAPI compatibility report;
- transactional SQLite tool registry persistence;
- validated SQLite run-event trace persistence with non-executing replay;
- trusted sync/async before/after execution hooks with snapshot-only, fail-closed semantics;
- dependency vulnerability auditing, CodeQL scanning, OpenSSF Scorecard supply-chain analysis, signed release build provenance, and SPDX SBOM attestations;
- remote asset 없이 생성되는 benchmark summary/history dashboard;
- versioned machine-readable artifact로 보존되는 scheduled compatibility smoke.

남은 큰 follow-up 작업:

- populate history views with dated live model/provider measurements;
- organization-specific policy/approval integrations.

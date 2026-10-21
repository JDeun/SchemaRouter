# Initial SchemaRouter paper ↔ current native retrieval (E0 audit)

Date: 2026-10-18. Issue #1530. Historical scientific source:
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://arxiv.org/abs/2608.21375).
This is a source-code trace and a very narrow first correction, **not** a
claim to reimplement the original paper or reproduce its 110-query result.

## Ownership stays unchanged

SchemaRouter is the graph/contract-backed catalog retrieval layer for
the **external agent**. The agent decides task decomposition, target tool,
arguments, use of output and follow-up steps. The host explicitly grants
and invokes execution only through its existing policy-bound pathway.
The graph is the internal typed ontology and may be persisted in various
stores, **not** the agent loop or a required graph DB.

## Paper-to-current implementation crosswalk

| Paper concept / step | Source-code evidence on main before this PR | Status |
| --- | --- | --- |
| Tool → Endpoint → Parameter → Field declarations | `models.py:217-229,300-316,451-470,724-738`; registry supports in-memory + SQLite `registry.py` | **Implemented** source contracts |
| DomainConcept ↔ semantic field / aliases | `FieldSpec.semantic_id/aliases` in `models.py:300-306`; `_CandidateIndex` indexes field aliases/semantic IDs in `planner.py:409-552`; `CompatibilityContext` models *explicit* semantic equivalences `capability_contracts.py:53-153` | Components exist; general query→concept graph traversal **not wired** |
| FieldGroup ↔ Intent projection | `QueryIntent.concepts` + `_select_fields_sync` / `_project_fields` in `planner.py:2819+,4329+` | Partial field projection; explicit paper intent-group graph structure **not identified** |
| Unit/type/qualifier matching | `FieldSpec`, `CapabilityFieldContract`, `compare_capability_fields` `capability_contracts.py:18-52,275+` | Implemented typed comparators; **not** graph-reranked default retrieval by themselves |
| SourceType + license + provenance | `ToolSpec.source_type/license` and `FieldSpec.source_type/license` `models.py:300-315,724-738`, `CapabilityCandidate` `models.py:954-980`; `EvidenceRequirements` `models.py:808+` | Metadata and evidence contracts **implemented**; do not assume license compliance from presence of labels |
| Versioned capability graph/edge builder | `capability_graph.py:18-210` builds typed producer→consumer dependency edges, `capability_snapshot.py:30-200` handles immutable graph snapshot/artifact | Implemented, but **separate graph purpose** from query↔concept↔field retrieval |
| Actual default query→K search | `SchemaRouter.retrieve_authorized` `runtime.py:3682-3740` → `SchemaPlanner.retrieve` `planner.py:937-960` → `_retrieve_from_intent` `planner.py:820+` → `_CandidateIndex` `planner.py:409-552`; default `KeywordAnalyzer` and `structural_retrieval=False` `planner.py:350-360,553-594` | Implemented **lexical+typed Top-K** with auth; not shown to run paper's intent/concept graph |
| Graph structure mode | `structural_retrieval` `planner.py:1618-1738` scores schema specificity / identifiers, not `capability_graph.build_capability_dependency_graph` traversal | Not equivalent to original concept graph |
| Graph-informed multilingual concept linking | Default query analyzer indexes tokens and declared aliases; #1339 frozen KO/JA initial required-route recall 0/160 on English-metadata corpus | **Gap requiring separate qualified work**, no automatic translation or benchmark retrofit |

## E0 experiment added by this PR

`scripts/research_declared_concept_graph_bridge_e0.py` creates a host-owned
strict **declared alias→semantic field edge** over existing
`SemanticEquivalence`, with exact whole-query lexical matching only.
The canonical target is accepted only if it appears in the
**passed-in current principal-scoped analysis registry**. It then
enriches `QueryIntent.concepts` and delegates to the native
`SchemaPlanner` and authority/field projection. There is no
new candidate creation, executable plan, model translation, network
access, permission, hidden-field disclosure or graph DB dependency.

No alias or field in this E0 bridge is inferred. A KO/JA source whose
English-only field semantic ID is **explicitly bound by the host** can be
retrieved; unknown/inexact/missing or hidden targets fail to enrich the
query. Strict declaration count/byte bounds, duplicate-alias denial,
source-version drift guard and EN/KO/JA original native-surface controls
are required. The result is only a narrow link in the paper's chain.

The production default, graph persistence, model planner, `#432` frozen
results, independent `#1346` validation, and v0.18 `#1356`
**HARD HOLD** remain unchanged.

## Next qualifications

- Implement graph-native concept→field-group/required-response-field
  derivation under an explicitly versioned source snapshot, with
  unit/qualifier/type and license/source constraints applied *before*
  K selection, and fail-closed policies.
- Establish a query-disjoint EN/KO/JA + OOD corpus with publisher-authored
  field and route gold, not a translation of previously exposed cases.
- Compare exactly matched K5/permission/snapshot conditions and report
  pre-agent route **and required field** recall, false accepts/refusals,
  actual schema/context tokens and p50/p95/p99 latency. Reuse #1477 E2
  once independent #1346 intake unblocks.
- Do not substitute an 'agent tool table of contents' wrapper for graph
  matching. The existing public `retrieve_authorized(...,k=5)` already
  delivers bounded candidate contracts.


## 2026-10-21 canonical-source audit update — M1 architecture acceptance

This updates the **audit**, not the independent product qualification, after
the source-owned G3/G4/G5 engineering changes. Inspected at main
`4e4a01fcae4008bdfd8a7bca41d4ef65583e9b2a`.
The original retrieval API and external-agent boundaries have not become
an autonomous agent or a default semantic router.

### Paper component → current home → wiring verdict

| Original paper step / typed relationship | Exact product/research code and proof | Verdict |
| --- | --- | --- |
| Source Tool/Endpoint/Parameter/ResponseField declarations | `models.py`, `registry.py`, `adapters/openapi.py`, MCP and OPTIMADE adapters; `tests/test_native_graph_three_real_adapters.py` builds one actual adapter-derived catalog | **Native declarations wired**, not identity/permission proof from vendor free text |
| Query → Intent/DomainConcept/declared alias | Default `planner.py` `KeywordAnalyzer` and lexical `_CandidateIndex`; **separate** `concept_retrieval.py::resolve_native_concepts` with `NativeConceptCatalog` | **Default lexical wired; owner-declared concept matching opt-in only**; no open-vocabulary EN↔KO↔JA translation |
| Explicit conjunctive FieldGroup → compatible response fields | `field_group_retrieval.py::retrieve_authorized_field_group` and `NativeSchemaPostingIndex.lookup_concepts`; `_complete_fields` / `compare_capability_fields` | **Opt-in pre-K conjunction implemented**, source/type/unit constrained, not default graph retrieval |
| SourceType / license / unit / qualifier and provenance | `models.py` `FieldSpec`/`ToolSpec`, `capability_contracts.py`, `semantic_attestations.py` pinned tool+endpoint originals; G5 match after source review | **Structural declarations/host claims**, no issuer authentication or legal license clearance |
| Semantic producer → required consumer inputs / ID propagation | `capability_graph.py::build_capability_dependency_graph`; `native_graph_index.py::NativeSchemaGraphIndex.build/lookup` reuses the canonical compatibility graph and proves a complete one-root/one-consumer binding, at most 4 typed required inputs | **Opt-in one-hop original-source binding**, not a general two-hop/multi-root execution DAG |
| Versioned query→concept→group index on complete catalog | `native_semantic_index.py::NativeSchemaPostingIndex.build` stores immutable semantic-ID inverted postings, route locations/fingerprints and registry-version snapshot digest; `NativeSchemaGraphIndex.build` adds canonical producer/consumer edges | **Indexed opt-in G5 structural lookup**, stale source fails closed; full catalog **build** still scans, not an incrementally refreshed production index |
| Current principal/data scope, availability, original fingerprint before K | `NativeSchemaPostingIndex.lookup` and `NativeSchemaGraphIndex.lookup` intersect source-semantic postings then independently recheck original endpoint fingerprint, RBAC, principal visible fields, read-only and availability before emitting candidates | **Wired for opt-in, not invoker authority**; tests enforce hidden identifier and unreviewed MCP `readOnlyHint` refusal |
| Top-K5 overflow and trustworthy ranking | G5 index returns `complete`, `no_proven_hit` or `over_k_unranked`; `_research_ranker` is separate, bounded to 32 **authorized, detached** candidates and returns `ranked_unverified` only | **Strict K5/no silent truncation**; no independently qualified general relevance ranker, no-fit calibration, production default change |
| Original default retrieval route | `SchemaRouter.retrieve_authorized` → `SchemaPlanner.retrieve` → keyword/lexical/typed scoring and top-K; never automatically invokes `NativeSchemaGraphIndex.lookup` | **Lexical default preserved**; the paper's full graph-powered default routing is **not implemented** |

### Opt-in original-adapter and negative controls actually present

`tests/test_native_graph_three_real_adapters.py` compiles actual
OpenAPI 3.1, MCP `tools/list`, and discovered OPTIMADE descriptors
into a **single** catalog. EN `case status`, KO `문의 상태`, JA
`問い合わせ状態` are **explicit host-approved aliases** of one field
group, not naturally inferred translations. A host-reviewed OpenAPI
identifier producer and MCP case read consumer form one typed binding;
an unrelated OPTIMADE endpoint must not be borrowed as a compatible root.

Negative controls: an unreviewed remote MCP read-only hint yields
`no_proven_hit`; a data-scope-hidden OpenAPI identifier prevents
the producer edge under the restricted principal; an invalid OPTIMADE
required-input JSON Schema cannot be silently weakened; registered
endpoint mutation makes the old index fail closed. The matching G5
research source also tests denied/absent fields, over-K and staged
authorization. All are **E0** declarations/fixtures, not live calls.

`scripts/benchmark_indexed_native_graph_g5_cpu_e0.py` measures
synthetic 5,100-noise-route indexing and warm CPU/RSS lookup independently
and refuses source-result drift. Its results must remain labeled as
synthetic CPU workload, not empirical third-party provider p95 or
independent task-success evidence.

### Audit disposition and remaining feature owners

- **Audit's source-to-code crosswalk, default-path trace, falsifiable
  opt-in controls and non-goals are evidenced above.** The audit can be
  administratively completed separately from unimplemented product features.
- [#1535](https://github.com/JDeun/SchemaRouter/issues/1535) owns
  independently qualified required FieldGroup completeness before K.
- [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) owns
  production-grade incremental catalog-wide graph index, 500/5000
  multi-source scale, multi-hop semantics, defensible >K5 ranker and
  validated default graph retrieval. Source-fingerprint matches are a
  necessary condition, not evidence of an authorized production deployment.
- [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) owns
  English-only metadata → actual KO/JA semantic transfer and negative no-fit;
  declared multilingual aliases do **not** solve that gap.
- [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) and
  [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) own
  independently authored source-native query/gold/permission approval and
  paired **actual agent final-task E2**. No new E2 score is present here.
- [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) stays
  release HARD HOLD. The original frozen #432 negative remains unchanged:
  SR-5 **29.19%** versus FULL **49.62%**, ORACLE **70.98%**.

**Evidence classification:** source-code/adapter-bound E0 audit. Do not
interpret administrative completion of #1530 as completion of M1 #1535,
#1560 or any independent commercial release/performance gate.

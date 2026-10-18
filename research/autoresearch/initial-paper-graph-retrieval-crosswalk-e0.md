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

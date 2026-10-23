# Original SchemaRouter paper → product Algorithm 1 parity: architecture decision

**Status:** source-code audit / action plan, **not a claim of production parity**  
**Date:** 2026-10-24  
**Source of truth:** [original paper's actual LaTeX](https://github.com/JDeun/paper_SchemaRouter/blob/main/paper/schemarouter.tex) (§§1, 3–4, Algorithm 1, §6), not follow-up CodeGraph experiments.  
**Code baseline:** `SchemaRouter/main` inspected 2026-10-24; exact public entrypoints and specific methods below.  
**Earlier audit:** [#1530 E0 code crosswalk](../../research/autoresearch/initial-paper-graph-retrieval-crosswalk-e0.md), completed as an **audit only**, not completed feature parity.

## Decision in ordinary language

**SchemaRouter has not become an unrelated project.** It still registers
heterogeneous tool/endpoint/parameter/field schemas, does bounded field-aware
retrieval/planning, preserves registered evidence metadata and separately
validates execution. Those are necessary elements of the original paper.

**But the original Algorithm 1 is not the default product retrieval path.**
The default uses an offline `KeywordAnalyzer` and a lexical/typed endpoint
candidate index, then ranks and truncates to K. Trusted concept→FieldGroup→
typed-graph retrieval lives behind **separate opt-in research APIs**. The
producer→consumer dependency-graph branch solves a related, *different*
problem and cannot substitute for the paper's concept→response-field
projection, intent-group recall safeguard and downstream evidence.

Original architectural objective: **preserve answer-critical field recall
while minimizing retrieved-context cost and retaining source, unit and
license evidence**. It was *not* minimize tool count, field count, menu JSON
bytes or make a small LLM perform multi-hop actions. The original paper
itself found that aggressively minimizing field count reduced final answer
accuracy (0.71→0.56 at very small downstream context-token savings).

### End-to-end boundary from the original paper

```text
User query
  → Understand: intent, concepts, explicit tool, source constraint, params
  → trusted schema graph: concept/alias ↔ required field group ↔ endpoint
  → source and provenance constraints + ranked candidate routes
  → recall-preserving field projection: identifiers ∪ concept fields ∪ intent groups
  → attach units, source type, provenance, license
  → return (tool, parameters, selected response fields, metadata) PLAN
  → external RAG/agent retrieves actual data and writes the answer
```

In the developed library, a **retrieval shortlist** is not an executable
tool call, and only the *explicit host-initiated* plan/execute boundary
can invoke tools after authorization, schema and fingerprint rechecks.
That is a safety-strengthening refinement, not a deviation from mission.

## Line-level crosswalk: paper Algorithm 1 vs inspected current main

| Paper requirement / algorithm step | Main code path and present capability | Verdict / falsifiable gap |
| --- | --- | --- |
| **1. Common graph schema** Tool → Endpoint → Parameter / ResponseField | `models.py` (`ToolSpec`, `EndpointSpec`, `FieldSpec`, `ParameterSpec`), `registry.py`, source adapters, `runtime.py::add_tool` | **Core implemented.** These are typed registered contracts; graph DB storage is optional. |
| **2. Understand(query)** → intent, concepts, parameters, source constraint, explicitly named tools | `planner.py::KeywordAnalyzer.analyze` is the **default** (`SchemaPlanner.__init__`); `analyzers/model.py::ModelQueryAnalyzer` is optional and sanitizes model proposals; `PlanRequest`/`QueryIntent` have concepts/arguments/preferred tools and evidence requirements | **Partial.** No default paper-style small-LLM intent/concept pipeline. Optional `ModelQueryAnalyzer` builds a `schema_catalog` for up to 128 endpoints, so that use mode is **not** the paper's schema-independent prompt. No equivalent fixed intent registry/group declaration is wired by default. |
| **3. Explicit named tool override** | `planner.py::_score_endpoint` + preferred tool/endpoint bonuses, `PlanRequest.preferred_tools`, `ModelQueryAnalyzer._sanitize` | **Related mechanism wired**, but a high score does not equal paper's unconditional `Resolve` override; must test absent, denied and conflicting named routes. |
| **4. Domain/Intent and required FieldGroup before K** | Default `planner.py::_retrieve_from_intent` scores `_semantic_recall_catalog`, sorts, emits `candidates[:k]`; `field_group_retrieval.py::retrieve_authorized_field_group` and `concept_retrieval.py::resolve_native_concepts` are opt-in | **Critical default gap.** Explicit conjunctive `{A,B}` requirements, completeness and source constraints are not proven as a mandatory pre-K gate in default retrieval. Tracked by **#1535**. |
| **5. Source constraint** (experimental / calculated / literature), unit, license, qualifiers | `ToolSpec`/`FieldSpec` metadata; `PlanRequest.evidence.source_type`; `capability_contracts.py` typed field comparator; opt-in `NativeDeclaredFieldGroup` source/license/typed requirements | **Partial.** Trusted declarations exist and specific opt-in methods check them. Paper-equivalent default **pre-selection** source and type filtering (rather than merely attaching evidence after choosing) needs targeted positive/negative tests. License string presence is not legal compliance. |
| **6. Concept/alias → canonical response fields** (`MAPS_TO_CONCEPT`, `ALIASED_AS`) | `FieldSpec.semantic_id/aliases`, lexical `planner.py::_score_endpoint`; opt-in `concept_retrieval.py` / `concept_graph_retrieval.py::retrieve_authorized_concept_graph` | **Critical default gap.** Owner-declared alias graph lookups exist separately; default does NOT run the original end-to-end query→concept→field-group graph traversal. Declared EN/KO/JA aliases are not automatic multilingual semantic transfer; see **#1339**. |
| **7. Deterministic recall-preserving fields** identifiers ∪ concept-match ∪ intent-required group | `planner.py::_project_fields` chooses `identifiers + matched_fields`, falling back to *all output fields* if no answer match; `_compile_candidate_sync` builds ToolCall | **Partial**. Recall-safe fallback is present, but the paper's explicit intent→FieldGroup **union** is not performed by default; conservative all-fields fallback is a different algorithm. Unqualified sparse field projection is not sufficient. |
| **8. Attach provenance, license and unit at field level** | `evidence.py::available_evidence`, `models.py::ToolCall.evidence`, `CapabilityCandidate` source/license + `FieldSpec` unit / qualifiers; executor evidence validation | **Contracts wired.** Downstream *answer-level source/license attribution* is owned by the caller/reader, not automatically guaranteed by a registered metadata field. An explicit reader contract + score is still needed. |
| **9. Emit executable tool/parameter/field/meta plan** | `runtime.py::plan` / `planner.py::_compile_candidate_sync` create typed `ToolCall` with declared arguments, fields, evidence and schema fingerprint; `runtime.py::retrieve_authorized` separately returns a bounded non-executing candidate shortlist | **Implemented as safe split APIs.** Model/host owns later invocation; executor rechecks permission, source and schema. The split is compatible with the paper if an opt-in user-facing end-to-end paper-aligned contract is demonstrated. |
| **10. Scaling with schema-independent intent prompt** | Default keyword analyzer is independent of inventory size; optional `ModelQueryAnalyzer` sends model a bounded `schema_catalog` of descriptors | **Partial / two different modes.** Do not claim paper's fixed small-LLM intent prompt merely because the offline default is cheap. A bounded schema-independent **model** understanding step must be separately demonstrated for that claim. |
| **11. Typed producer→consumer graph** | `capability_graph.py`, `native_graph_index.py`; `concept_graph_retrieval.py` opt-in; recent #1741–#1744 E0 research | **Useful research extension, not a substitute.** Producer ID→consumer parameters is orthogonal to paper query concept→output field projection. One-hop, bounded, not an autonomous agent or default. |
| **12. Paper's downstream objective** correct answer + retrieved context tokens + provenance/license citations | Paper experiments: 110 materials-science tasks, 0.71 reader accuracy (overlapping CIs), 227 retrieved-context tokens vs 2,066 fetch-all, 62% schema-only license citation. New E0 studies: schema JSON bytes/Qwen tokenizer tokens; #432 independent frozen SR-5 29.19% vs FULL 49.62% | **Unresolved on new product.** These numbers have *different fixtures, units and evaluator/reader*. A 30% **schema menu** tokenizer reduction is **not** the paper's 9× **retrieved-result context** reduction, quality preservation or independent answer trustworthiness. |

### Three separate graphs/metrics — do not conflate

1. **Original paper's conceptual schema graph:** user intent and natural-language
   domain concepts mapped to canonical required response fields and grouped
   endpoint/tool contracts, units, provenance and license. **Primary mission.**
2. **Product capability dependency graph:** a typed field/identifier producer
   can satisfy another endpoint's required input. Useful and safe for graph
   route planning; optional extension, **not the whole original schema graph**.
3. **Agent trace / CodeGraph frontiers:** what model tools to show on each
   turn, call timing and continuation. Only a **downstream agent integration
   experiment**; may be deleted or changed without changing the original
   SchemaRouter thesis.

## Risk assessment

- **Not a wrong product:** unifying source adapters, versioned original
  contracts, field-aware plans, source/policy validation, provenance and
  runtime binding are reusable substrate for Algorithm 1. The stronger
  default permission boundary is a desirable feature beyond the paper.
- **Real mission displacement risk:** many capability ingestion adapters,
  execution policies, complex action/agent benchmarks and producer-graph
  iterations can consume development time while leaving the default
  **concept→field-group→field projection** path incomplete.
- **Scientific claim risk:** a favorable E0 schema/menu-token result says
  nothing about new independent downstream reader answer accuracy.
  Frozen #432 negative outcomes and KO/JA zero-initial-recall cases
  must remain visible; paper's original N=110 fixture was author-made
  and compared a different system configuration.

## Re-aligned delivery order and acceptance gates

**P0 — Preserve the valid product, freeze terminology** (**now**):
`main` remains 0.17, old default `retrieve[_authorized]`, plan/execute
safety and adapter contracts unchanged. Do not merge opt-in research
branches into default without acceptance. Document the 3 distinct graph
purposes and the four metric units: *selected schema bytes*,
*tokenized schema/menu text*, *retrieved data/reader context tokens*,
*whole agent input+output tokens*. No unqualified single % savings.

**P1 — Qualify paper's semantic-field path before K** (**#1535; highest
feature priority**): implement on the *existing* source-authorized graph
index and planner boundary, not a new router/agent loop. Host-reviewed
query→intent/concept→required FieldGroup with canonical semantic IDs and
approved aliases. Verify all required response fields and identifier
bindings under unit, qualifier, source type, license, actual principal
visible fields and schema fingerprint **before K**. Explicit statuses:
`complete`, `no_proven_hit`, `budget_unsatisfied`,
`over_k_unranked`. Unknown/ambiguous/source-disjoint cases must not
fabricate a match; partial field hit ≠ complete plan. Scripted cases:
A-only, B-only, A+B, incompatible unit, hidden B, denied B, mismatched
producer ID type, multiple providers/aliases, missing parameter,
over-K and EN/KO/JA declared aliases.

**P2 — Assemble opt-in **paper-complete** plan, not only a route shortlist**
(**#1560 + #1535**): verify that the opt-in pipeline produces selected
`ToolCall(tool, endpoint, bound_arguments, response_fields, evidence)`
with *identifiers ∪ concept-match ∪ required intent FieldGroups* and
schema/policy/source proof, without treating retrieval as execution
authorization. Reuse `SchemaPlanner`, `ToolCall`, original registry,
the existing executor, and `NativeSchemaGraphIndex`; no redundant
catalog/executor. Pin snapshots and preserve source values; no auto
call sequencing as a requirement. Use actual source-defined examples,
not only CRM producer fork.

**P3 — Restore the paper's downstream evaluation contract**
(**#1339 + #1346 + #1477**): pair same query/gold, reader,
principal and source snapshots across `FULL`, original-style
`prompt-all`, strong schema-aware lexical, opt-in paper-complete G5.
Report required **response-field recall**, exact tools and parameter
validity, correct source-type/provenance/license, OOD abstention,
retrieved **data**/reader-context tokens, end-to-end latency and final
answer correctness. Report separately *schema menu tokens* and *whole
agent tokens*. The source-only Qwen3 tokenizer study is a supplementary
metric, never a replacement. Independent source/publisher/author data
remains **BLOCKED_EXTERNAL #1346**, and no unseen E2 claim until intake.

**P4 — Product/default promotion** (**#1560 + #1356**): only after
qualified safety, EN/KO/JA mixed-language, source accuracy, task quality
and CPU/RSS non-inferiority. Run default-vs-opt-in snapshot-paired
regressions and plan-vs-execute authorization checks. Keep v0.18
HARD HOLD until actual release gates.

## Immediate work allocation — no unnecessary new umbrella issue

- **#1535**: owner of missing conjunctive/recall-preserving typed FieldGroup
  completeness **before K**, including paper's explicit field union.
- **#1560**: owner of existing ontology index, opt-in graph→typed plan
  composition, no parallel catalog, snapshot and promotion.
- **#1339**: owner of undeclared/multilingual alias coverage and false
  matches (do not treat exact declared alias lookups as full translation).
- **#1346**: owner of genuinely independent reviewed task/field/provenance
  ground truth; maintain BLOCKED_EXTERNAL.
- **#1477**: owner of one shared existing native executor/evaluation harness,
  paper-style downstream response-field coverage and full agent success.
- **#1356**: v0.18 release HARD HOLD.
- **#1530** is a **closed audit**, not proof of delivered Algorithm 1.

**Evidence decision:** product foundations and much research were valid;
the specific original Algorithm 1 paper-to-default integration is still
incomplete. Prioritize P1/P2 ahead of additional frontier prompt tinkering
or more variants of the same synthetic producer fork.

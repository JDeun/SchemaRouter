# AutoRAG (Marker-Inc-Korea) vs SchemaRouter — Related Work

> **Research / wiki-ready note**, 2026-10-25 · Tracking: [#1750](https://github.com/JDeun/SchemaRouter/issues/1750) and [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) · Authoritative upstream snapshot: [AutoRAG `e6bfe03`](https://github.com/Marker-Inc-Korea/AutoRAG/tree/e6bfe03ce6da955317f1277264661334286bf176) (2026-10-24 UTC).  
> This Markdown lives in SchemaRouter's Git repository; **it is not yet a published page of GitHub's separate `.wiki.git` repository**. Mirror after Wiki write access is available. Research relevance is documented, not a benchmark result.

## Executive assessment

**Relevance: Medium–high for retrieval/fusion and experimental methodology; low for direct core-architecture integration.** The upstream repository contains **two different AutoRAGs**, and they must not be conflated.

1. **Current AutoRAG Agent 2.0 (TypeScript, root):** a document librarian/agent. It federates CLI-backed/local document retrieval, combines multiple methods, merges evidence, optionally reranks, reads retrieved originals, and returns curated citations. It is **not** SchemaRouter's original-paper schema/parameter/field router.
2. **Legacy AutoRAG AutoML (Python, `legacy/`, maintenance mode):** evaluates/optimizes alternative RAG pipelines against a QA/corpus set and implements traditional retrieval metrics and hybrid RRF. Its scoring methodology is reusable *in concept*; its dataset/object model is not a SchemaRouter typed-tool gold oracle.

AutoRAG focuses on **which document chunk to read and cite**. SchemaRouter Algorithm 1 must choose **which source-owned ToolSpec/Endpoint/Parameter/ResponseField contract** can satisfy a complete semantic FieldGroup for a particular principal, respecting original tool versions, permissions, source and license, exact typed arguments, and fixed Top-K=5. Documents are not tool schemas; a relevant passage is not proof of a safe or executable tool.

## Primary-code observations (pinned to the upstream revision)

| Upstream component | Observed design | Research transfer and limits |
| --- | --- | --- |
| [`src/retrieval/engine.ts`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/src/retrieval/engine.ts), [`selection.ts`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/src/retrieval/selection.ts) | Parallel-method retrieval; narrow method/source selection, scope filtering, merger and optional reranking. | Evaluate architectural separation between **candidate generation / eligibility / scoring**. Never interpret datasource selection or path scoping as SchemaRouter's principal authorization. The engine explicitly notes that configured datasources are searchable without a permission setup. |
| [`src/retrieval/merger.ts`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/src/retrieval/merger.ts) | Per-method min–max normalization; dedup by `source + id`; bounded corroboration bonus; retains distinct chunks. | A *comparison baseline* for union/score-fusion of authorized retrieval candidates. For SchemaRouter, dedup key must preserve **original route+field+source fingerprint / scoped witness**, not merely a shared title or semantic-ID string. Filtering must precede every model-visible shortlist. |
| [`src/retrieval/rerank.ts`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/src/retrieval/rerank.ts), [`docs/rerank.md`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/docs/rerank.md) | Optional post-merge relevance reranker; external model is trusted-config opt-in; provider failure gets diagnostics and no silent model substitution. | Compare a **typed-schema-descriptor-only reranker** against existing lexical/E5/RRF on the *same eligible menu*. No consumer secret data or hidden fields may enter reranker inputs. Reranker output must be verified as exactly 5 authorized original candidates or abstention; no unreviewed fallback or default-product promotion. |
| [`src/retrieval/evidence-id.ts`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/src/retrieval/evidence-id.ts) | Normalized stable evidence IDs over method/source/position/text; preserves opaque upstream IDs when appropriate. | Relevant to **stable source-native identity**, reproducibility and joined observation receipts. SchemaRouter already uses source and endpoint fingerprints/snapshot IDs; reuse those rather than adding a second identifier registry. |
| [`docs/retrieval-memory.md`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/docs/retrieval-memory.md) | Stores judged cited evidence as advisory cross-session context; documentation explicitly says it **does not reorder results** or override current evidence. | Potential future **offline feedback dataset**, not an access-control source and not evidence of online learned ranking. Enforce provenance, TTL/source churn, deleted-source and hidden-field invalidation; do not persist principal-private candidates across access changes. |
| [`legacy/autorag/evaluation/metric/retrieval.py`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/legacy/autorag/evaluation/metric/retrieval.py) | Recall, Precision, F1, MRR, MAP, nDCG implementations, with groups of equivalent gold IDs. | Adapt evaluation **definitions**, not blindly copy code. For a SchemaRouter query, gold can be equivalence classes of fully valid source/field/route sets: report route recall@5 separately from **entire required FieldGroup / parameter-binding correctness**, zero forbidden exposures and calibrated OOD abstention. |
| [`legacy/autorag/nodes/hybridretrieval/hybrid_rrf.py`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/legacy/autorag/nodes/hybridretrieval/hybrid_rrf.py) | Weighted/hyperparameterized reciprocal-rank fusion on lexical/semantic candidate lists. | SchemaRouter **already has** the source-authorized fixed-K5 RRF path; compare without reimplementing a second fusion engine (see below). |
| [`docs/permissions.md`](https://github.com/Marker-Inc-Korea/AutoRAG/blob/e6bfe03ce6da955317f1277264661334286bf176/docs/permissions.md) | Agent filesystem mutation approval modes. | **Do not import** into SchemaRouter's trust model: agent file-edit approval is not a proof of native source data scope, policy, license or operation safety. |

## Existing SchemaRouter assets: prefer reuse

- `src/schemarouter/native_semantic_index.py` (`NativeSchemaPostingIndex`): versioned full-tool-catalog semantic postings, closed scoped source verification, canonical field/unit comparison and incremental journal refresh at ≥5,000 heterogeneous routes.
- `src/schemarouter/native_graph_index.py` (`NativeSchemaGraphIndex`): exact producer→consumer typed graph edges, authorization/health/scope first and the existing **private opt-in G5 research ranking** callback.
- [Previous fixed-K5 authorized RRF comparison](../autoresearch/authorized-hybrid-fixed5-rrf-e0.md): already implements lexical/E5/hybrid RRF scoring behind the source-native snapshot. **Do not port AutoRAG's RRF to replace it.**
- [G5 overflow ranker](../autoresearch/g5-authorized-overflow-ranking-e0.md): existing 32-candidate limit and strict original route-offset acceptance.
- [Direct indexed FieldGroup ranking PR #1749](https://github.com/JDeun/SchemaRouter/pull/1749): adds the same opt-in **bounded 6–32 candidates / exactly K5** contract for direct field-group retrieval. No independently established ranker gain.
- [External agent E2 #1477](https://github.com/JDeun/SchemaRouter/issues/1477): **reuse** `scripts/agent_utility_generated_common.py::FrozenCorpusExecutor` and paired scorer. Avoid another agent loop.
- [External benchmark intake #1346](https://github.com/JDeun/SchemaRouter/issues/1346): actual provider/publisher-authored, legally usable, unexposed tasks/route/field/permission gold—not synthetically generated questions pretending to be independent confirmation.

## Measurement crosswalk and preregistration

**Unit of evaluation:** one publisher-authored query × principal × immutable current native catalog snapshot × language. Same source permissions and K=5 for all comparisons, including when eligible candidate count exceeds 32. Evaluate supported, ambiguous, unauthorized and out-of-domain/no-fit cases separately.

| Metric | Definition / caveat |
| --- | --- |
| Supported complete route recall@5 | Portion of supported tasks whose chosen 5 includes an independently accepted original route/path satisfying **all required typed fields**. A single relevant field does **not** count as a success. |
| MRR@5, nDCG@5 | Rank-sensitive metrics on publisher-validated *equivalent valid route groups*; pin gain and equivalence handling before seeing holdout outcomes. |
| Typed plan safety | Exact input/output parameter source binding, original record provenance, same-record scalar/unit semantics; zero forbidden/hidden/outdated/license-incompatible emissions. |
| OOD / denied | False positive suggestions, unsupported-disposition accuracy, abstain rates and correctness by type; an unverified ranker abstention **is not** proven no-fit. |
| Latency/resources | Per-stage p50/p95/p99 CPU/wall time, peak RSS, schema byte disclosure, model input/output tokens, real **data-context tokens** and downstream agent task outcome on the same hardware. |
| Agent E2 | Paired downstream task completion, source citation/license correctness, tool argument correctness and safe side effects using **existing** #1477 executor. |

Suggested comparison arms (no new engine): baseline conservative K5 abstention; existing authorized lexical; existing injected semantic E5; existing authorized RRF; optional schema-descriptor-only reranker. Run on ≥500 and ≥5000 source routes plus genuine 6–32 eligible-candidate scenarios. Preregister model, input descriptor format, budget, tie-breaks, threshold and holdout protocol. Avoid using QA synthesized from SchemaRouter fixtures as publisher-independent gold.

**Failure expectations:** if permission, scope, license, health, source fingerprint, accepted output, original field completeness or current snapshot changes during ranking, fail closed. Never permit an external ranker to create a route, reorder unauthorized evidence or convert its ranking into executable authority. A retrieval optimization is not a v0.18 release sign-off.

## Implementation recommendation

**P1 — do now:** retain PR #1749's opt-in boundary and baseline tests; record this crosswalk and issue [#1750](https://github.com/JDeun/SchemaRouter/issues/1750). No unverified AutoRAG port.

**P2 — only with independent gold:** adapt the metric definitions and run the existing authorized lexical/E5/RRF/optional rerank arms under source-pinned, principal-paired gold. Report negative or neutral results as faithfully as improvements. Do not adjust holdout after seeing answers.

**P3 — if measured benefit:** implement a small independent research adapter via existing `DecisionBackend` / research ranking seam; never fork the registry, native graph engine, ACL system or executor. Source data-reading remains outside SchemaRouter's product contract.

## Licensing and publication notes

AutoRAG root and `legacy/LICENSE` are **Apache-2.0**; SchemaRouter is **MIT**. Architectural ideas and metric definitions can be independently implemented. Copying upstream code or assets requires appropriate Apache-2.0 license and notice/attribution review; do not label code copied from Apache as solely MIT. This note links rather than reproduces substantial upstream source.

This is **wiki-ready source-controlled research**, not actual GitHub Wiki publication; the GitHub connector's repository contents API does not write `SchemaRouter.wiki.git`. Sync this Markdown to GitHub Wiki with an authorized Wiki Git writer; track that deliverable under #1750. Keep [#1356](https://github.com/JDeun/SchemaRouter/issues/1356) release HARD HOLD.

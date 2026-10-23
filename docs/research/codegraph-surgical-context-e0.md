# CodeGraph-style surgical graph context: scoped E0 byte-control study

**Reviewed 2026-10-23 · [#1711](https://github.com/JDeun/SchemaRouter/issues/1711) · M5 · E0 synthetic, nonexecuting · no default change**

## Prior art vs SchemaRouter (do not conflate the problems)

| Question | [CodeGraph](https://github.com/colbymchenry/codegraph) | SchemaRouter |
| --- | --- | --- |
| Indexed entity | Code symbols, call sites, file relationships and agent navigation | Registered source-native operations, output field semantic IDs and typed producer→consumer bindings |
| Intended savings | Avoid repeated repository file discovery and navigation | Avoid redundant model-visible schema material while preserving the **same** source-authorized route set |
| Trust boundary | Developer's local code index, agent integration | Original source fingerprint, principal/data-scope, current policy, fixed K=5, separately authorized host invoker |
| Safe transfer | **Surgical, reference-first context packaging**, test whether details can be loaded only when needed | Reuse `NativeSchemaGraphIndex` and `retrieve_authorized_concept_graph`, never import code AST edges as tool authority |
| Out of scope | Not an equivalent substitute for a source-owned capability graph | No new AST index, graph DB, learned edges, agent invoker, default router or authorization bypass |

**Upstream provenance:** `colbymchenry/codegraph` MIT (`LICENSE` blob `31c84c9c80d953a0571b69af15cf815f22c5f2b6`); README reviewed 2026-10-23 at Git blob `baac93178c98b6efb9794a5668d42f3f0f0882f7`. The README's author-reported seven-repository, four-run-per-arm architecture QA (2026-08-05) claims **88% fewer tool calls**, **62% fewer processed tokens**, and **44% lower cost**, but **NOT** in SchemaRouter. Importantly, the same README notes **larger residual context occupancy** in CodeGraph's multi-turn sessions despite fewer cumulative processed tokens. Thus context serialization bytes alone cannot predict agent context-window use, tool-call efficiency or cost. [Source and methodology](https://github.com/colbymchenry/codegraph#benchmark-results).

## Preregistered fixed E0 control

**Hypothesis:** keeping verified typed graph route references while deferring *model-visible full tool definitions* could reduce initial serialized bytes without changing selected routes, their complete bindings, visible output fields, or any source/authority status. **Falsification:** either an unauthorized/stale path survives, a source/route/field receipt differs, or the reference has no measurable byte advantage on the supported control. A byte win by itself does not justify model deployment.

- **Unit:** one query × one original synthetic source catalog/index snapshot × one principal × fixed `K=5`. Both arms use the **same** returned `NativeConceptGraphSelection` and guarded `capture_authorized_agent_tool_surface` (including visible fields and fingerprint receipts); the experiment introduces no second planner.
- **FULL:** selection receipts plus the existing principal-scoped, selected native tool definitions (names, descriptions, parameter schemas).
- **SURGICAL:** **the exact same** status, snapshot/version, route IDs, each route/tool/endpoint fingerprint, full producer-field→consumer-parameter bindings, required semantic IDs, visible output names and false quality/authority flags; deliberately **omits tool definitions**. `requires_source_schema_materialization=true` and `tool_call_ready=false` must not be confused with invokable tools.
- **Safety:** selected routes must occur in the guarded model-visible view with matching native fingerprints. An **outer, continuous authority witness, policy-content receipt and canonical principal claims** span the graph selection and separately scoped tool capture, including no-hit cases; checking only the registry version was insufficient. Every producer-side binding field must still be visible in the captured source view. Replacement or in-place policy narrowing, principal mutation and stale-source drift fail closed. `no_proven_hit`, denied and over-K preserve their status and export **zero route IDs**; no hidden candidate metadata and no arbitrary Top-5 truncation. The compact form has no generalized public disclosure endpoint. This is not a transaction across concurrent host threads.
- **Corpus:** one source-native CRM producer with two required root identifiers and one fully-bound consumer, repeated with owner-declared EN/KO/JA aliases; missing producer identifier (`no_fit`), denied principal (`denied`), six eligible consumers (`over_k`). Synthetic source control only; no source calls, user payload, model gold or executable agent.
- **Measurement:** `len(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))` for each arm; ratio `SURGICAL/FULL`. Repeat the same call to check deterministic results; compare selected path parity and all receipt fields. No tokenizer or LLM is run: **processed tokens, money, downstream tool calls and final-task success: NOT MEASURED**.

Reproduce from the repository root:

```bash
python -m scripts.research_codegraph_surgical_context_e0 --json
python -m pytest -q tests/test_research_codegraph_surgical_context_e0.py
```

## E0 observed result (2026-10-23 local synthetic)

| Preregistered case | FULL UTF-8 JSON bytes | SURGICAL bytes | Ratio | Status / path |
| --- | ---: | ---: | ---: | --- |
| joined EN | 1,825 | 1,028 | 0.5633 | `complete`, 2/2 route IDs and full bindings identical |
| joined KO | 1,825 | 1,028 | 0.5633 | `complete`, 2/2 identical |
| joined JA | 1,825 | 1,028 | 0.5633 | `complete`, 2/2 identical |
| incomplete producer (`no_fit`) | 362 | 384 | 1.0608 | `no_proven_hit`, 0 paths |
| forbidden principal (`denied`) | 362 | 384 | 1.0608 | `no_proven_hit`, 0 paths |
| six consumer alternatives (`over_k`) | 364 | 386 | 1.0604 | `over_k_unranked`, 0 paths |

Supported, source-matched pairs saved **797 bytes (43.67%)**, not model tokens. Negative/empty cases instead added **22 bytes** due to the explicit reference-materialization indicator; they do not demonstrate savings. Direct comparison deterministically reproduced identical bytes and bindings. Tests separately verify policy narrowing between graph and tool-surface reads is rejected (including in-place edits), principal claims cannot change across the two reads, old-index failure upon original source revision, and new source index differing by snapshot ID while keeping the same authorized selection.

The full context is still **not executable authority**; only an independent host policy/argument/source check could invoke. The surgical form additionally omits parameter JSON Schema details and therefore **cannot be used directly as a function/tool call interface**. Any future lazy materializer must be a separate, scoped, source-revalidated and metered protocol; its costs are presently excluded. Thus the isolated byte reduction may overstate actual integrated savings once materialization is required.

## Go/no-go and follow-up

**E0 disposition: byte-effect demonstrated on a small paired synthetic slice; transfer to real model/provider efficiency UNPROVEN.** Keep #1711 in M5 until the appropriate review; do not change fixed K, shipped default, independent no-fit decision or the #1356 release hold. No claims that CodeGraph's self-reported performance transfers here.

**Next E1 decision (separate):** same frozen native provider inventory, owner-reviewed scope/principal, source revisions and budget; compare FULL, lexical SR-5, typed G5 and surgical-reference packaging with actual model/agent and schema-materialization costs. Include real token receipts, tool/latency/task success by EN/KO/JA and unsupported tasks, failed original provider calls, immutable source evidence and explicit inconclusive verdicts. #1346's publisher-disjoint E2 remains independently blocked and is not inferred from E0.

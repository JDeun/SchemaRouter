# Matched-K5 G5 versus source-scoped schema lexical — research E0

Preregistered 2026-10-24 before ANY new matched-K5 result. Parent #1560,
stacked Draft #1741. Reuses existing `build_fixture`, `GROUP`, `ACTOR`,
`ALIASES`, original-source `exhaustive_source_fork_reference`,
`NativeSchemaGraphIndex.lookup_shared_root_forks`, and scoped source-contract
byte function from #1741. No new product path or graph algorithm.

## Frozen arms and denominator

For each native catalog 500 / 5000 routes, normal / mixed (source policy,
hidden field, wrong input type, different source/license, optional root),
and EN/KO/JA declared aliases, produce exactly 12 paired source-snapshot
queries. Both arms have **the same current authorization, source/visibility,
license/source-type, read-only and K=5 max**:
- G5: opt-in indexed, source-attested strict typed shared-root 3-route fork.
- **Source-scoped, schema-aware lexical K5**: rank authorized original
  per-route schemas by predeclared query/FieldGroup semantic tokens from
  name, description, output fields, parameter metadata. Text relevance
  ONLY, no graph edges, join provenance, ranker ML, or hidden gold IDs.
  Lexical receives the SAME host-approved FieldGroup (semantic IDs,
  source_type and license) as G5; do not handicap it to tool names alone.
  Ties resolved by stable route ID; always emit 0–5 distinct native routes.
  Do not auto-complete missing producer identifiers via oracle/gold.

## Source correctness, cost eligibility and negative controls

Independent original registry source oracle expects precisely the
three-route fork. A successful retrieval arm must include ALL THREE
original authorized routes (required producer and two consumers), not
just the first leaf or any same-name decoy; verify no hidden or unlicensed
route, no source drift, no K breach. Distinguish both complete, G5-only
complete, lexical-only complete, both miss. Exposed compact native
source-contract UTF-8 bytes are compared **only if both sets are complete**.
A lower-byte menu missing any one original route is NOT an efficiency win.
Measure per-query selected menu counts/bytes and naive text ranking;
do NOT call these bytes tokenizer counts or multi-turn agent costs.
No executable permission is conferred by candidate retrieval.

Preplanned comparison limitation: ONE developer-authored shared-root
fork and only three owner-authored language aliases, repeatedly measured
under inventory size and scope perturbations; N=12 cells is NOT 12
independent natural tasks. The source-aware lexical scorer is a
predeclared plausible comparator, not proven state-of-the-art lexical
retrieval (BM25 dense retrieval or commercial service). Never infer a
population accuracy improvement or causal effect for arbitrary G5
queries. This is a stricter same-K controlled test than #1741 unbounded
FULL bytes, but still E0 synthetic.

Report every negative and positive cell, absolute bytes, shared-correct
denominator and refusal path. Reuse frozen #1741 3-route / health
revocation original evidence; do not discard previous negative Qwen3.5
terminal failures, #1740 default-indexed cost overhead, or independent
v0.14 FULL>SR negative evidence. Independent external E2 #1346 and
paired real source agent #1477 remain blocked; #1356 v0.18 HOLD.

## Post-measurement — first qualifying GitHub Linux result

Measurement code head `83fa367728eff5bfebf76d1a6a941f3622248295`.
[GitHub Actions run #40030754793](https://github.com/JDeun/SchemaRouter/actions/runs/40030754793),
all **4/4** strict scoped-paired source jobs succeeded.
Archived JSON artifact IDs:
`12534976621` (500 normal), `12534966787` (500 mixed),
`12533824174` (5000 normal), and `12534497900` (5000 mixed).
The preregistered report output contains EN/KO/JA rows for every cell.

| Catalog | Original authorization view | G5 complete | Lexical complete | G5 routes | Lexical routes | G5 source schema bytes | Lexical source schema bytes | G5 byte reduction on same-success menus |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 500 | normal | 3/3 languages | 3/3 languages | 3 | 5 | 2,050 | 3,264 | 37.19% |
| 500 | mixed | 3/3 languages | 3/3 languages | 3 | 5 | 2,050 | 3,536 | 42.02% |
| 5000 | normal | 3/3 languages | 3/3 languages | 3 | 5 | 2,050 | 3,264 | 37.19% |
| 5000 | mixed | 3/3 languages | 3/3 languages | 3 | 5 | 2,050 | 3,536 | 42.02% |

**12/12** owner-authored catalog/scope/language cells are paired
*source-oracle-complete* in both arms, using equal strict maximum K5.
The shared-success cost denominator is therefore **12/12** here, rather
than dropping lexical failures. Both source authorization and a revoked
consumer were revalidated: neither arm disclosed a revoked source
route. No tool execution or model action occurred.

The schema-aware lexical comparator receives the same host-approved
FieldGroup, source_type/license, current source-visible inputs/outputs
as G5. It chooses exactly 5 native routes rather than the three
needed for this one root/two-leaf fixture. The graph's typed
connectivity excludes two extra **relevant-looking but unnecessary**
route schemas; the effect is a **descriptive serialized native
schema-byte reduction** while preserving this specific fork. It is
not independent proof that every lexical method would expose those
two extras: a better learned BM25/reranker/relational method or
tuned lexical K could produce another Pareto point.

***Scientific limits:*** The 12 cells reuse **one owner-designed
gold topology** across EN/KO/JA aliases and two catalog sizes, plus
one group of adversarial source-visibility decoys. Do not assign
independent-trial confidence intervals or treat the 37/42% schema
byte reduction as an LLM model token saving. The bytes are
serialization of existing read-only original native source
contracts, and none of the Qwen agent correctness failures
were repaired by this new analysis. A reproducible,
host-attested G5 K5-vs-K5 cost/required-route result in this
construction IS supported; a general cross-provider accurate
and cost-saving agent paper claim remains unproven.
External author/source-disjoint task+field+permission E2 #1346,
paired genuine source agent #1477 and release HOLD #1356
remain mandatory.

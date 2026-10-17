# Authorized lexical + semantic RRF fixed-K5 — source-scoped E0 candidate

**Research condition only**: `EVAL-FIXED5-OPTIN`. Does not change public
`SchemaRouter.retrieve()`, `retrieve_authorized()`, native provider
execution or any original #432 result.

## Concrete comparison candidate

This completes the third **implemented** routing arm needed by the paired
evaluation contract (#1482):

- `lexical_k5`: existing source-authorized native lexical ranking.
- `e5_k5`: existing opt-in `AuthorizedFixed5DecisionSelector` with a
  supplied backend. The nickname does **not** force the backend to be E5,
  and no actual E5 model is loaded in this E0 PR.
- `hybrid_k5`: new `AuthorizedHybridFixed5Selector` which calls existing
  authorized lexical ranking and the same bounded semantic decision bridge
  under the **same** `AuthorizedAgentToolSurface` snapshot.

For every currently authorized route, compute the **fixed** score

```
RRF(route) = 1/(60 + lexical_rank(route))
           + [1/(60 + semantic_rank(route)) if in selected semantic shortlist]
```

No learned thresholds or DEV-tuned weights. Select top
`min(5, number_of_authorized_routes)` by descending score, tie-broken
by lexical rank and stable original route ID. All semantic suggestions
are restricted to registered principal-scoped native routes, rechecked
against source fingerprints and authority witness before and after model
inference. A semantic abstention uses an explicitly labeled lexical
fallback; **it does not imply calibrated no-fit**. A partial semantic
shortlist receives an explicitly labeled *non-gold lexical fill* so K=5
stays fixed without accessing fixture gold.

The model receives original EN/KO/JA query bytes and only the
source-authorized descriptors already selected by the #1473 comparator.
Field-scoped catalogs never expose arbitrary publisher free prose.
Neither candidate backend nor RRF selector can compile or execute
source-native provider operations. The existing agent fixture and output
redaction from PRs #1479/#1480 are reused in the E0 integration test.

## Quality and scope boundaries

- Using a fixed formula is **not evidence it beats lexical or E5**. Some
  providers/requests can get worse; only preregistered, genuinely paired
  task success with independently authored EN/KO/JA/OOD gold can settle
  this. Historical ServiceNow/Open-Meteo DEV rankings were contradictory.
- The semantic backend is injected; the dedicated tests use a no-model
  `CallableDecisionBackend`. This is **not an actual pretrained E5 score**,
  multilingual generalization claim, or an independently scored provider
  agent benchmark.
- Source-policy checks are non-atomic during concurrent remote effects.
  The research selector has no native invoker authorization or calibrated
  abstention threshold; producer-bound execution safety is still separate.
- The added full-catalog source retrieval and per-query decision can cost
  CPU/tokens. Do not promote a latency claim without GitHub Actions
  Linux p50/p95/p99 measures.
- The native external author review/split/gold requirement remains #1346.
  Release PR #1356 is **HARD HOLD**; frozen #432 outcomes unchanged.

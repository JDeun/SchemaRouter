# #1339 — Counterfactual trusted-operation **oracle** over real embedding Top-10 (DEV)

**Scientific scope:** This is NOT a trained operation classifier or an actual host-authenticated authorization policy. It asks a *conditional* question: **if** an independent trusted host could reliably declare the user's operation and independently verify endpoint operation contracts, how many earlier Top-1 retrieval mistakes would be recoverable from the top 10? We use explicit author-written oracle labels to establish a diagnostic **upper bound**, not a solution that currently classifies free-form Korean/Japanese requests.

## Frozen real-model source and exact original candidates

Replay the existing successful 2026-10-15 [Actions run #38729631022](https://github.com/JDeun/SchemaRouter/actions/runs/38729631022), with exact MiniLM and E5 Small original report SHA-256 pinned in `benchmarks/1339-multilingual-model-scale-frozen-manifest.json`. The [source-integrity auditor #1438](https://github.com/JDeun/SchemaRouter/pull/1438) must validate all 84 original cases, 13/100/250/500 catalog identities, 48 supported and 36 unsupported, cross-model gold assignments, original ranking, and dev-only scope **before** applying this filter. All 672 model × catalog × case predictions are immutable.

Original 500-candidate Top-1 accuracy: MiniLM **39/48**, E5 **39/48**; Top-10 recoverability ceilings: MiniLM **47/48**, E5 **44/48**. No reranking can recover absent Top-10 candidates. No arbitrary similarity threshold is chosen; prior [#1438](https://github.com/JDeun/SchemaRouter/pull/1438) proved scalar-score overlap on this author-written set.

## Predeclared *simulation*, not deployment-ready route classifier

- Explicit catalog-route operation manifest for 13 authored read-only base routes, plus **only** the 18 generator-defined read-only operation stems. These labels describe a controlled synthetic fixture; route names in untrusted production APIs MUST NOT be treated as trusted operation declarations.
- A separate, explicit author-labeled user-operation oracle keyed by the 14 existing source case *families*. This is NOT inferred from query text, embedding score, target gold or prediction. In actual deployment the host must independently verify both user intent and route-operation manifest.
- Filter each existing real model Top-10 list to routes whose declared operation **exactly equals** the trusted source-oracle request operation. Preserve original relative ranks, never introduce new routes or invent hidden fields. If request operation is unrepresented or unknown, result is an **abstention**.
- `dev_stress.museums.routes` means **lookup a previously stored route**, not navigate in real-time; `maps.directions` is **directions**. A correct host operation declaration could distinguish these two metadata-confused routes, subject to Top-10 inclusion. Similar-looking tool names are not an authorization credential.
- Counters separately report supported recovery, nonrecovered Top-10 misses, wrong compatible Top-1, conditional no-fit of *source-authored* unsupported cases and language strata. Because these negatives were written with **missing operation classes**, an observed zero accepted negative would be *tautological*, not classifier no-fit performance.
- Source identities, whole case rows and negative examples archived. Single committed method; no gold-route used to choose the matched candidate.

## Hard limitations

This counterfactual assumes a **perfect human/host oracle** it does not implement. It does not show that `infer_operation_intent`, E5, MiniLM or any other model can supply trustworthy operation intent. It does not call `execute_selective_plan`, update any `DeclaredOperationFitPolicy`, launch tools, invoke agent graphs, or prove that the correct operation means the right arguments/fields/task completion. It is explicitly NOT an independently-authored heldout, authentic third-party capability schema, calibrated no-fit classifier, real host identity, SLO or release gate. Historical 0.14 #432 negative finding remains unchanged.

GitHub Actions read-only Ubuntu Linux CPU, strict source digest and 672-case fail-closed parity. No downloads of model weights, GPU, paid API or external coding agent. A useful next test must use independently labeled operation intents **not derivable from fixture/gold**, authentic capability contracts, and paired denied/no-call + executable agent task success. **#1339/#1346 open, v0.18.0 #1356 HOLD.**

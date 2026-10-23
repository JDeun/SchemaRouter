# Source-native G5 paired Qwen/Open-Meteo E1 — first observed run

**Date:** 2026-10-23 (UTC). **Classification:** exposed, self-authored E1 DEV; **not** independent E2, release, commercial provider qualification, or a general routing benchmark.

## Fixed run and source provenance

- [GitHub Actions run 39877863640](https://github.com/JDeun/SchemaRouter/actions/runs/39877863640) for PR #1714; PR head `48c98d14fe8aa711b1e8b37baa50187d88262ff2`, Actions pull-request checkout source revision `f99191c73aaef90605aeac4cbae5c52fdbc305a6` (merge revision, **not** the PR branch head).
- [Sanitized paired G5 E1 artifact](https://github.com/JDeun/SchemaRouter/actions/runs/39877863640/artifacts/12469836477), artifact ID `12469836477`, GitHub ZIP digest `sha256:72c981c072d43bd3b665ec35421c37c437bb1a222bca9e1d2e7352881183a0e8`. Action artifact expires 2026-12-22; this note preserves the non-sensitive diagnostic classification.
- Frozen `Qwen/Qwen3-0.6B` revision `c1899de289a04d12100db370d81485cdf75e47ca`, CPU greedy; actual public Open-Meteo geocoding/weather HTTPS; EN/KO/JA disclosed host-authored prompts; noncommercial Free API research only.
- Same two original source routes across all three arms: `all_visible`, `lexical_k5`, `concept_graph_optin`. K5 is a disclosure ceiling; a two-route source **cannot establish a token-reduction claim** under K5. No gold-derived aliases/route selection, no model-driven execution authority.

## Original observed nine episodes

| Language | All-visible FULL | Lexical K5 | Source-native G5 |
| --- | --- | --- | --- |
| EN | Geocoding HTTPS `connect_timeout` | First geocoding validated, **premature final** | First geocoding validated, **premature final** |
| KO | **Pass:** two validated provider calls + strictly grounded final | Geocoding HTTPS `connect_timeout` | Geocoding HTTPS `connect_timeout` |
| JA | First geocoding validated, **premature final** | First geocoding validated, **premature final** | Geocoding HTTPS `connect_timeout` |

Raw runner report originally returned `E1_MEASURED_DEV_NOT_E2` with `all_visible=1/3`, `lexical_k5=0/3`, `concept_graph_optin=0/3`. **These are observed descriptive completion counts, not a fair paired comparison of routing conditions**: four of nine episodes terminated on independently verified original-source HTTP connect timeouts. Among the remaining five, four stopped after geocoding with a premature model final, and only one succeeded. No hidden provider values, raw model prompts, coordinates, weather readings, or request arguments are persisted here.

## Post-run decision (recorded before successor run)

1. Keep all nine original diagnostic rows and immutable original artifact. Do not reinterpret a provider timeout as a graph selection/model failure or claim G5 improvement from this contaminated sample.
2. In the revised paired evaluator, classify any original-source `geocode_http_*` / `forecast_http_*` failure as `INCOMPARABLE_SOURCE_FAILURE`, preserve sanitized per-arm rows and set `task_success_rate=null`. Ordinary model `premature_final` remains a valid model task failure in a source-available episode. Source-value drift separately remains `INCOMPARABLE_SOURCE_DRIFT`.
3. Read the actual pinned Qwen token receipt on each model turn (`model_input_tokens`, `tool_schema_tokens`, `model_output_tokens`) per episode; missing or partial receipts are `null`, **never imputed zero**. Legacy solo-E1 output stays unchanged. Until a subsequent measured run, no token or CPU-cost savings are claimed.
4. Rerun the same *unchanged host-authored DEV tasks* with these validity gates. Treat repeated source transport failure as a reason to investigate provider availability and paired design **before any prompt tuning or graph-ranking optimization**. A source-available negative model outcome is a legitimate development finding, not a request to edit the gold/scorer.

The verified G5 source-authority/typed-route implementation can progress to code review independently of task-success promotion. Parent #1535/#1560/#1477 remain constrained by independent #1346 E2; release PR #1356 stays HARD HOLD. SchemaRouter's MIT licensing does not license commercial Open-Meteo Free API traffic on behalf of downstream adopters.

## Second original-provider run — after evaluator and token-accounting correction

- [GitHub Actions run 39879598633](https://github.com/JDeun/SchemaRouter/actions/runs/39879598633), `pinned-qwen-real-native-provider` job `120173746574`: **successfully executed** on PR branch head `7864e2df05d7b1e01699b63394ffd056b2869148` (Actions pull-request source checkout revision `13592aeb79af3387022ca56e4853243a366ed7bc`; these are not the same SHA).
- [Sanitized original-source paired report artifact](https://github.com/JDeun/SchemaRouter/actions/runs/39879598633/artifacts/12469928501), artifact ID `12469928501`, ZIP digest `sha256:4d0aad2772e86393de30a2e2c68285529d1339e6d4d18dc228dfe640bda1825e`. Expires 2026-12-22. No raw model turns, tool arguments, coordinates, provider values or private gold are in this note.
- Same frozen `Qwen/Qwen3-0.6B` revision, EN/KO/JA cases, original Open-Meteo source and three disclosed arms. Real model-reported `model_input_tokens`, `tool_schema_tokens`, `model_output_tokens` receipts are **complete for every one of nine episodes**. No dollar or reduction estimate follows from this two-route, incomplete-run sample.

| Language | Arm | Original source / agent result | Input tokens | Schema tokens | Output tokens |
| --- | --- | --- | ---: | ---: | ---: |
| EN | all-visible | Geocoding validated; premature final | 1161 | 714 | 88 |
| EN | lexical K5 | Geocoding validated; premature final | 1161 | 714 | 88 |
| EN | G5 | Geocoding `connect_timeout` | 402 | 230 | 41 |
| KO | all-visible | **Completed both native calls and strict final** | 1944 | 1071 | 134 |
| KO | lexical K5 | Geocoding `connect_timeout` | 544 | 357 | 43 |
| KO | G5 | Geocoding validated; premature final | 913 | 434 | 90 |
| JA | all-visible | Geocoding `connect_timeout` | 547 | 357 | 41 |
| JA | lexical K5 | Geocoding validated; premature final | 1199 | 714 | 87 |
| JA | G5 | Geocoding `connect_timeout` | 420 | 230 | 41 |

Corrected evaluator status: **`INCOMPARABLE_SOURCE_FAILURE`**; `task_success_rate=null`. Four independent actual-provider connection timeouts prevent comparable denominators. Four source-available episodes ended with `premature_final` after valid geocoding; one reached strict final. The latter are genuine diagnostic agent-task failures but **not evidence that a particular retrieval arm is worse** in the contaminated nine-row aggregate. Token totals across episodes with different numbers of source calls/model turns do **not** establish context savings or cost superiority.

### Next major experiment, preregistered separately from these two baselines

Separate externally induced HTTP transport failures from model-dependent premature finalization using the **already existing** single idempotent read-only transport retry and one verified-evidence follow-up allowance. Apply identical budgets to every arm. Preserve source-failure invalidation, original native inputs, strict final oracle, untouched prompts/gold, no elevated tool authority, and model/source revisions; record the actual retry attempts and number of follow-up prompts. This is a bounded **operational robustness cohort**, not a G5-vs-FULL routing improvement claim, independent E2, or a replacement for the two no-intervention baseline runs. If Open-Meteo stays unavailable, publish another explicit incomparable result rather than adjusting the model or silently simulating provider replies.

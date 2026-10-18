# BFCL V4 public-to-public LIVE category transfer — separate pair-fit classifier E1

**2026-10-18, preregistered before any live-category outcomes; #1339 / #1477.**
Source [UC Berkeley Gorilla / BFCL](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard) publisher commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, Apache-2.0.

## Observed problem and falsifiable question

[PR #1519](https://github.com/JDeun/SchemaRouter/pull/1519) established that a pinned multilingual E5 ranks candidate function names strongly on original publisher PUBLIC BFCL cases, but forced choice refuses 0/240 irrelevant requests; one fixed two-token guard refused 21/200 supported; score-based cutoff calibrated to ≤10% no-fit false-acceptance incorrectly refused 47/100 supportable odd-ID cases. **Do not retune those same scores to obtain a favorable headline.** Function ranking and the decision to abstain are different tasks.

A new diagnostic uses **function-by-function supervised relevance**, rather than a scalar threshold on the winning embedding alone, to see whether an independently learned pair classifier can improve **joint** supported admission and unsupported refusal under the same single cutoff criterion. It must still lose if supported recall is worse; the experiment is hypothesis falsification, not model promotion.

## Source pins and held-apart PUBLIC categories

All sources fetched from pinned upstream commit, original raw Git-blob identity checked using `sha1(b"blob <bytes>\0" + raw)`; never float main, silently replace/translate, or inject labels at inference. Training and cutoff categories:
- `BFCL_v4_multiple.json` original blob `83643fa853e7a29a50e7303b0279284c37dd63c8`: 200 multiple-function **supported** requests with actual original function-name gold `possible_answer/BFCL_v4_multiple.json` blob `1f2f1fbfd9b7c8859ef5a92d6c18b0a6b2bc2663`.
- `BFCL_v4_irrelevance.json` original blob `0077629949f2d52734cef2f110b0d040d8c47554`: 240 no-tool requests.
- Even-numbered original case IDs train only (100 supported questions, 120 unsupported; one positive original gold function per supportable case, all other offered sibling functions and all no-tool functions negative). Odd IDs are cutoff calibration ONLY (100 supported, 120 unsupported).
- **Evaluation categories not used for model fit or threshold:** `BFCL_v4_live_relevance.json`, upstream Git blob `1b0190995f4554b980da2dd7ab15195f4e047e62`, 16 original relevant tasks; and `BFCL_v4_live_irrelevance.json`, blob `547f60220b546ea5c864815dbb310b2f46ec0f43`, original irrelevant tasks. Count is source-derived and reported, not silently sampled. Only one-turn publisher conversations supported; invalid files fail closed. These live categories are **not live service executions**.

**Caution:** all BFCL cases are PUBLIC and may appear in model pretraining; they share benchmark authorship and design even across disjoint categories. Consequently LIVE-category evaluation is **not privately independent publisher-source E2**, does not prove EN/KO/JA, and cannot calibrate a production threshold. We had already examined presence/shape of LIVE files before score; this is not blinded evaluation.

## Exactly two fixed arms

Use real, fixed local `intfloat/multilingual-e5-small` at HF revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, CPU, `trust_remote_code=False`, `E5CachedEmbedder`. Both arms see the same query and **exactly the same publisher function descriptions, names and parameter descriptions**, and no label. One function-level feature vector is exactly `[E5 cosine, distinct content-token Jaccard, clipped shared-token-count/5]`; tokens inherited from already committed fixed #1519 `_words`. **No function-count feature**, since the train categories themselves have a multiple-vs-single-function confound.

- A: raw max E5 cosine per request + fixed cutoff calibrated using only 120 odd-ID negative requests, threshold immediately above 13th highest negative value (so at most 12/120 calibration false accepts; ties fail closed).
- B: `StandardScaler` + `LogisticRegression(C=1.0 default, class_weight='balanced', solver='liblinear', random_state=0, max_iter=1000)` on even-ID **per-function pairs**; request relevance is max offered original function probability. **Same** public calibration-negative cutoff rule applied to B (separately to probability scale).
- Neither arm is allowed to choose a live-data-derived threshold, use live labels in training, emit a model-generated route not in source, execute tools, or change production default. Label accuracy on live-relevance **function names is not known**: report only "at least one tool" relevance / refusal, NOT official BFCL answer AST or action success.

## Original publisher no-tool structural cases and source messages

Live publisher source inspection revealed two legitimate source shapes NOT covered by
the previous internal artificial fixtures: system-prefaced user tasks, and
`live_irrelevance` requests with **zero offered functions**. These findings
concern byte-format validity, not model scores.

- Restrict relevance features to the **last user content**; any earlier
  publisher message (`system`, `assistant`, `user`) is not promoted to a
  trusted host instruction. This may remove useful task context; the result is
  a last-user-message fit diagnostic, **not full official BFCL task evaluation**.
- Report `irrelevant_zero_candidate_functions` and
  `irrelevant_with_candidate_functions` separately, without dropping any
  original cases. No offered functions means **structural no-call**, and those
  samples are expressly **excluded from model no-fit denominators**. Otherwise
  a model would earn credit for requests it never examined. Conditional
  predictor FPR/true refusal is computed only when at least one original
  publisher function was actually offered. If none exists, abort scoring
  rather than fabricate model quality.
- Preserve exact file SHA and case count; no new prompts, function gold,
  unseen task labels, tuned score cutoffs or per-source exemptions.

## Fixed output and stopping

Store original source SHA hashes, stable model SHA, positive and negative denominators separately for calibration and LIVE evaluation, supported admitted/false-refused and unsupported falsely-accepted/correctly-refused for A/B, with real Linux CPU runtime. Publish negative outcomes unmodified even if trained B loses to raw A. Do **not** adapt prompts/features/thresholds from these observed scores.

No authenticated principal, source ACL/RBAC native integration, EN/KO/JA, real provider tool, argument correctness, multi-turn agent, private task-author holdout or E2 compliance. #1346 independent E2 **0/19**, A02/R05 not verified, model/default and v0.18 #1356 HOLD.

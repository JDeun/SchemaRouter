# BFCL V4 LIVE — source-pinned CPU cross-encoder no-fit E1

**Status: predeclared exploratory E1, awaiting actual model/source workflow.** Tracks [#1582](https://github.com/JDeun/SchemaRouter/issues/1582). Neither independently authored held-out #1346 nor a live external provider/agent E2 #1477.

## Why this trial exists

The prior original public BFCL LIVE paired-fit study (PR #1577) admitted **8/16** supported queries and falsely admitted **144/880** unsupported queries (after familywise correction 4/16 and 91/880). **75 of those 91** residual false accepts occurred on singleton function menus. This does **not** justify another menu-size penalty or simply increasing the cutoff; both can increase false refusals.

One preregistered cross-encoder experiment compares each original final-user query (not untrusted system preface) against each offered publisher function's original name/description/parameter fields. Frozen Hugging Face model **`cross-encoder/ms-marco-MiniLM-L6-v2`**, revision **`c5ee24cb16019beea0893ab7796b1df96625c6b8`**, CPU-only, no newly trained head. Model may have seen public BFCL examples. Model relevance does **not** certify execute authority or typed field coverage.

## Frozen protocol — no live-label threshold selection

- Original publisher [BFCL V4 snapshot](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard/bfcl_eval/data), with source Git blobs and SHA-256 fingerprints verified by preexisting `fetch_original_data` and `load_live_source` readers.
- Calibration: precisely the **120 odd IDs** in original `BFCL_v4_irrelevance.json`; for each original case, take maximum raw cross-encoder score over offered source functions. Nonempty menus required. Use **strictly above the 13th-highest** odd negative score to target at most **12/120** (~10%) calibration false admission. No LIVE score or label can adjust this cutoff.
- Evaluation: untouched original publisher LIVE `live_relevance` **16** supportable cases, `live_irrelevance` **884** unsupported cases, **4 empty offered menus** excluded from cross-encoder scoring and counted as structural no-call, leaving **880** candidate-bearing negatives.
- Publish accepted/false-refused **and** false-accepted/correctly-refused in the same frozen 16/880 denominators. Break down both dimensions by **1, 2–4, 5–12, 13+** offered functions. No per-row task text, gold, model logits, coordinates, provider payload, secrets or raw model responses.
- Report actual initial model load wall time, CPU inference time, Linux peak RSS and paired-function count. Guard against infinite/NaN scores, duplicate BFCL source fields, altered source blobs, unsupported source shapes and unbounded candidate-pair volume.

## Decision policy

- A result can *diagnose* whether cross-encoder rescoring reduces singleton-menu false admission without unacceptable loss of supportable recall or excessive GitHub Actions Linux CPU cost; no chosen uplift/latency target is retrospectively invented after seeing the report.
- Failed import/pinned model revision unavailable, provider HTTP failure, source drift or resource/time budget exhaustion is a **blocked or failed experiment**, not no-fit success.
- All historical negatives remain recorded. Keep frozen #432 intact. Never change production router defaults or declare native provider task success from model-only pair comparisons. v0.18 [PR #1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains **HARD HOLD** pending independent gates.
- Preserve failed/neutral outcomes and link exact-head source run/artifact when available; only then select whether to continue work on #1582.

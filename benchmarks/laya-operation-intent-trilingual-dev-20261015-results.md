# Native Laya EN/KO/JA operation-intent DEV — negative result (2026-10-15)

> **Status: NON-PROMOTABLE.** This is an authored exploratory development dataset,
> not independent validation. No authorization or tool execution was performed.

## Immutable inputs and executable provenance

- Raw GitHub Actions run: [38745998518](https://github.com/JDeun/SchemaRouter/actions/runs/38745998518).
- Actual **real local** Laya CPU artifact: [11978677115](https://github.com/JDeun/SchemaRouter/actions/runs/38745998518/artifacts/11978677115).
- Source commit for real inference: `5cd268b9fe2db14a1dbf6906116c1be7e44fd962`; follow-up changes remove an unused import and make subsequent costly runs manual. There was no metric or question tuning.
- Previously authored 72-item DEV source file:
  `benchmarks/operation-intent-trilingual-dev-20261015.json`,
  SHA256 `18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7`.
- **54 supported** (18 EN, 18 KO, 18 JA; nine operation kinds) and **18 unsupported** (6 per language, including negation, meta/how-to, compound commands and unrelated commands).
- Pinned runtime package: **laya 0.4.7**, Python 3.12.15, requested CPU device, four CPU inference threads, a single resident checkpoint at a time. Native router selected `english` and `multilingual` checkpoints. **Weights revision/hash and effective checkpoint device were not independently attested** by this run; PyPI version is pinned but that does not make the model-weight artifact fully reproducible.
- **Arm A:** actual `LayaDecisionBackend` type-safe single `choice` over nine fixed English operation descriptions. No veto or confidence cutoff.
- **Arm B:** separately run native `Router.predict` of the **same `choice` and a new typed `noul` question**: Does the original message affirmatively request exactly one actionable operation (not negated, multi-action, explanatory, out-of-domain)? A fixed, preregistered **illustrative 0.5** probability cutoff rejects any lower score. Native `noul` is not a calibrated no-match probability.
- Prior v0.11 full 16-choice and BGE winner-only `noul` configurations remain historically **rejected** and untouched. The new two-question research experiment does not retroactively revise them.

## Real measured results

| Metric | A: Laya choice | B: Laya choice + typed noul |
| --- | ---: | ---: |
| Supported exactly correct | **36/54 (66.7%)** | **2/54 (3.7%)** |
| Supported wrong operation, accepted | 18/54 (33.3%) | 0/54 |
| Supported **false refusal** | 0/54 | **52/54 (96.3%)** |
| Unsupported **false acceptance** | 18/18 (100%) | **1/18 (5.6%)** |
| CPU per-request p50 | 215.68 ms | 387.47 ms |
| CPU per-request p95 | 917.41 ms | 1,081.33 ms |

The paired arm's **raw** `choice` matched 36/54 too; its rejection step accepted only two supported requests. **The low false-accept rate was bought by rejecting almost all supported requests.** It is **not** evidence of a safe gate.

| Supported accuracy per language | A: choice | B: choice + noul |
| --- | ---: | ---: |
| English | 13/18 (72.2%) | 2/18 (11.1%) |
| Korean | 10/18 (55.6%) | **0/18** |
| Japanese | 13/18 (72.2%) | **0/18** |

- One unsupported English case (`unsupported-en-4`, transfer funds to bank) was falsely accepted by the `noul` condition and mapped to a **search** operation.
- The two supported cases accepted by `noul` were `supported-en-create-2` and `supported-en-update-2`.
- The native model's `noul` probability for most explicit Korean/Japanese supported requests was close to zero despite clear affirmative instructions.
- Peak process RSS: **4,998.46 MiB**. Total wall time including loads: **86.42 seconds**.
- Latency is **not a clean steady-state inference benchmark**: automatic language routing with `max_loaded=1` and interleaved EN/KO/JA cases causes checkpoint swaps, evictions and reloads. The English choice p95 was 7,557.77ms while Korean/Japanese choice p95 values were 557.07ms/222.35ms. Do not compare with a warm resident model on another runner as equivalent hardware.

## What was and was not verified

**Verified:** Actual Laya weights were downloaded and CPU native predictions completed; typed `choice` and typed `noul` both returned parseable responses; all 72 previously authored cases were measured twice; explicit supported/unsupported denominators and per-case outputs were uploaded.

**Not verified:** Exact HF weight snapshot digest, independent held-out quality, real hosted Jev parity, authentic 500-tool catalogs, calibrated probability, authorization safety, actual agent/tool execution success, or production performance. GitHub CI's 17 fake-router parsing checks are contract tests, not extra model performance cases.

## Engineering decision

**Reject both evaluated configurations for product promotion.** Laya's raw choice is insufficient on this DEV cohort, and its paired noul veto excessively refuses good requests. Do **not** change the 0.5 threshold, model question or corpus *post hoc* and claim a rescue or independent gain. A new preregistered hypothesis must use disjoint evaluation inputs, distinguish required operation intent from actual tool capability, and separately attest model checkpoint hashes and CPU cost. A hosted Jev comparison requires explicit credentials and a different cost/transport stratum.

Keep **#1313, #1291, #1339, #1346 open** and **v0.18 release PR #1356 HOLD**.

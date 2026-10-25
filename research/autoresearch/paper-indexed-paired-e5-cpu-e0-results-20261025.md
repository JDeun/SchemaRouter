# Native direct-index K5: genuine pinned E5 paired CPU result (synthetic DEV)

**Evidence tier:** `REAL_PINNED_E5_CPU_INDEXED_PUBLIC_SYNTHETIC_DEV_ONLY`
**Issue:** #1560 · **Draft PR:** #1753 · **Fixture:** original synthetic 24-service
EN/KO/JA G5 cohort (27 supported, 3 unsupported), reused without changing
gold or source route IDs.

## Executed evidence and reproducible receipt

- GitHub Actions workflow run:
  https://github.com/JDeun/SchemaRouter/actions/runs/40146422767
- Published JSON artifact:
  https://github.com/JDeun/SchemaRouter/actions/runs/40146422767/artifacts/12580722501
- Artifact digest: `sha256:0debcc16ba63045293505cc98c82b3333d2181435cef64b67274623cdd293f69`
- GitHub PR head for this workflow: `21ed18233cb543a620013a6c191dcb14537575f8`.
- Report's `git rev-parse HEAD` on default pull_request checkout:
  `fbd8ba3a242581616c3254c8119e325066994641` (**GitHub PR synthetic
  merge checkout**, not to be confused with the source branch head).
- Original native source snapshot:
  `3a127af4bb1cb20cdd517787ce3f5779f5d0b56bb48a3468e9170f2197dcd7b3`.
- Model: `intfloat/multilingual-e5-small`, revision
  `fd1525a9fd15316a2d503bf26ab031a61d056e98`, Linux x86_64,
  Python 3.12.15, PyTorch CPU 2.14.1+cpu, 384-dimensional encoder.
- Model load measured ~5723.7 ms (excluded from the per-query times below).
- Both jobs in the dedicated Actions workflow passed; no-model stage ran
  20 pytest cases, Ruff and Pyright and the 30-case CLI.
- The scorer obtains expected routes from the disclosed original fixture
  **only after** source-verified candidate selection; the real E5 model
  receives only the currently authorized route IDs and visible status fields.

## Same-source retrieval quality by language

| Arm | EN Recall@5 | KO Recall@5 | JA Recall@5 | Total supported recall |
|---|---:|---:|---:|---:|
| First-five source order (non-product control) | 1/9 | 1/9 | 1/9 | 3/27 |
| Fixed lexical route-token overlap (non-product control) | 9/9 | 1/9 | 1/9 | 11/27 |
| **Actual pinned E5-small CPU** | **9/9** | **8/9** | **9/9** | **26/27** |

| Arm and language | MRR@5 | NDCG@5 |
|---|---:|---:|
| Lexical EN | 1.0000 | 1.0000 |
| Lexical KO/JA (each) | 0.0556 | 0.0701 |
| E5 EN | 1.0000 | 1.0000 |
| E5 KO | 0.7167 | 0.7575 |
| E5 JA | 0.8056 | 0.8547 |

Paired lexical→E5 change: **15 rescued** and **0 regressed** among
the same 27 disclosed supported tasks. This is a strong *within-fixture*
engineering signal for multilingual ranking, not evidence of a general
publisher-independent win. The 3 OOD tasks in each arm yielded a nonempty
shortlist; this is **not** a calibrated no-fit/unsupported classification
experiment and cannot be converted into an unsupported error-rate claim.

## Exact Linux CPU timing from this one run

Whole typed indexed lookup inclusive of principal/scope/recheck and optional
synchronous ranker (ms); same job, sequential workloads, cold model loading
excluded.

| Arm | p50 | p95 | p99 | mean |
|---|---:|---:|---:|---:|
| Unranked indexed source | 14.61 | 15.12 | 17.15 | 14.77 |
| First-five callback | 14.65 | 14.78 | 15.07 | 14.64 |
| Lexical callback | 14.63 | 14.89 | 16.71 | 14.74 |
| Real pinned E5 callback | 40.22 | 42.60 | 120.69 | 44.19 |

This is **one** GitHub Actions runner, one order, 30 synthetic queries;
no randomization, confidence intervals, query-independent speed claim,
full model cache warm/cold characterization, context/schema token budget
measurement or production latency SLO. Per-arm time includes repeated full
authorization and typed source checks; do not label it model-only latency.

## Remaining work / strict boundaries

1. Source-independent, publisher-authored gold and contractual tool semantics
   (#1346) **before** an independent ranking claim.
2. Exact same-principal/field/operation cohorts and controlled reader/agent
   execution through the existing harness (#1477); no new homemade executor.
3. Distinguish unknown/no-fit and OOD threshold calibration; an arbitrary
   E5 five-item shortlist on OOD is not support evidence.
4. Broader 500/5000 route scale and >32 qualified-route handling; current
   E0 native callback **abstains** when more than 32 candidates qualify.
5. Paired repeated CPU/token benchmark with workload order control; unchanged
   product default, no PR merge, v0.18 #1356 remains HARD HOLD.

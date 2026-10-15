# Real CPU results — open-source routing design patterns (2026-10-15)

> **Research only — all four arms NOT PROMOTABLE.** This measures local
> implementations inspired by Semantic Router and LlamaIndex, **not**
> the original third-party software or any true agent execution. The 72
> already-public, self-authored requests remain **DEV**, never independent
> holdout or calibrated no-match evidence.

## Input lock and actual execution

- Original prior EN/KO/JA development corpus:
  `benchmarks/operation-intent-trilingual-dev-20261015.json`
  SHA-256 `18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7`.
- 54 supported (18 each language, 9 operations), 18 unsupported (6 each
  language including negated, multiple-operation and unrelated requests).
- **Real GitHub Actions Linux CPU:** [38749636821](https://github.com/JDeun/SchemaRouter/actions/runs/38749636821)
  - **Raw 72-row-per-arm JSON:** [artifact 11980486661](https://github.com/JDeun/SchemaRouter/actions/runs/38749636821/artifacts/11980486661)
  - Preregistered experimental code at `896b73b5e6cec167291c2274566b762c3080aca8`.
- Local MiniLM bi-encoder:
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Local multilingual cross-encoder, Apache-2.0:
  `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
- Hardware reported: 4 CPUs, 4 PyTorch threads, Python 3.12.15,
  peak process RSS **1,774.93 MiB**. Wall time **17.72 seconds** including loads.
- Neither model weight snapshot revision/digest was attested.
  Time measurements are within one shared model session: cross-encoder
  latency columns include query encoding and the prototype calculation
  performed earlier in the same iteration. Do **not** interpret them
  as isolated comparable service latencies.

## Four prespecified local method arms

| Arm | Exactly correct supported | Wrong supported | Supported false refusals | Unsupported false accepts | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1: Multilingual example max-cosine, forced | **30/54 (55.6%)** | 24/54 | 0/54 | **18/18 (100%)** | 13.71 |
| A2: Examples, cosine >= 0.65 and margin >= 0.03 | **9/54 (16.7%)** | 13/54 | **32/54 (59.3%)** | **7/18 (38.9%)** | 13.71 |
| B1: MiniLM original descriptions Top-3, independent cross-encoder rerank, forced | **33/54 (61.1%)** | 21/54 | 0/54 | **18/18 (100%)** | 52.34 |
| B2: Same rerank; selected-route retrieval cosine >= 0.65 | **1/54 (1.9%)** | 0/54 | **53/54 (98.1%)** | **0/18 (0%)** | 52.34 |

- **Top-3 candidate recall ceiling** from the B1 raw artifacts was
  **52/54 (96.3%)** supported operations. The actual cross-encoder rerank
  got only 33/54, despite usually having the gold operation among candidates.
  A generic passage-ranking model is *not* a reliable operation-fit selector.
- **A1 language breakdown:** English 14/18 (77.8%),
  Korean **2/18 (11.1%)**, Japanese 14/18 (77.8%).
  Three exemplars (EN/KO/JA) per operation did not ensure uniform coverage.
- **B1 language breakdown:** English 9/18 (50.0%),
  Korean 12/18 (66.7%), Japanese 12/18 (66.7%).
- **A2 accepted all six Korean unsupported cases** while wrongly refusing
  3/18 Korean supported, and falsely refused 16/18 English supported.
  This diagnostic threshold is not calibrated across languages.
- **B2 correctly refused all 18 unsupported cases** but incorrectly refused
  **53/54** supported — a catastrophic false-refusal tradeoff.
- The forced A1 and B1 arms always choose a route and thus mechanically
  accept all 18 unsupported items; this does not imply their models could
  never abstain with a different independently trained classifier.

## Context from prior experiments (NOT matched hardware trials)

- Previous forced MiniLM English-description operation categorization:
  **37/54** supported correct, **18/18** unsupported accepted.
- Previous forced E5 Small: **41/54** correct, **18/18** unsupported accepted.
- Prior Laya local `choice`: **36/54** correct, **18/18** unsupported accepted.
- Previous conservative regex DEV hypothesis: **52/54** correct, **0/18**
  unsupported accepted on these author-written examples; test phrases favor
  this lexicon, and this is *not* independently validated performance.
- These historical results concern different prediction architectures.
  Do not compare process time or memory as if same runner/model session.

## Decision and untested requirements

**Reject all four tested configurations for production promotion.**
Better candidate recall alone does not ensure operation-level correctness.
A fixed similarity or reranker-score cutoff cannot be adopted from these DEV
examples; a credible independent calibration and frozen confirmation protocol
must measure false accepts and false refusals together. A separate permission
and verified final-operation guard remains mandatory.

For future trials: independent real user paraphrases and truly unsupported
requests, authentic 100/250/500 provider tool schemas, query/option
role-specific training or task-fit classifier, independently held-out threshold
calibration and downstream no-call behavior. Do not optimize on the frozen
v0.14 #432/#424 material or claim external gate #1346 completion.

**Keep #1291, #1339 and #1346 OPEN and v0.18 #1356 HOLD.**

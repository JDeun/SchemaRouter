# Original-paper direct native Top-K5 — paired ranking DEV (E0)

**Date:** 2026-10-25 · **Issue:** #1560 · **Parent:** Draft PR #1749
**Code:** `scripts/research_indexed_paired_ranking_dev.py`

## Distinct question

Original-paper Algorithm 1 must filter **source-complete/authorized native
fields before K5**, then decide which five verified tools are useful. PR #1749
adds a bounded research-only callback for that final selection. This experiment
measures whether the same fully qualified 24-route field index can distinguish
useful *direct* endpoints under (a) no ranking, (b) first-five, (c) a frozen
lexical rule, and (d) an **optional genuine CPU E5** decision backend.

It intentionally differs from the already implemented G5 producer/consumer
graph tests. Direct field postings have no producer→consumer argument bindings.
Do not transfer direct-posting results into G5 graph success claims.

## Frozen source and cases; no independent-gold claim

- Reuse **exactly** the 24 original `SERVICE_NAMES`, 9 trilingual supported
  intentions (27 cases), and 3 trilingual OOD intentions from
  `scripts/research_g5_e5_overflow_cpu_dev.py`. No generated/relabelled gold.
- Every `service_<name>.read` source is a registered read-only tool with the
  identical source-owned `service.status` typed field and licensed synthetic
  source. The original subject `reader` must pass the existing allow rule.
- Per-query host declaration specifies the shared field group. This is
  intentionally synthetic: original `Understand(q)` is **not** validated here.
- Model input is limited to already authorized route IDs plus selected visible
  field names, using the same `ResearchIndexedFieldDecisionRanker` as #1749.
  Expected service routes are available exclusively to the offline scorer,
  not to the model, query preprocessor, index, or ranker.
- The default source index returns `over_k_unranked`, **zero** candidates.
  It is not a normal failing score. First-five and lexical are explicitly
  *control* policies, not shipping defaults. Lexical casefolds NFKC, splits
  snake-case route tokens, and ranks overlap plus stable pre-ranked order;
  no translation is inferred or tuned.
- Evaluation reports **retrieval** Recall@5, MRR@5, NDCG@5 by language and
  OOD nonempty-shortlist frequency. The latter is *not* a calibrated no-fit
  false-positive rate. The paired rescue/regress count uses identical cases.
- Whole-index lookup wall-clock p50/p95/p99 is measured per arm in the same
  process; not a reproducible cloud latency SLA and not an agent-token cost.

## Commands

No model download, contract/metric checks:
```bash
python -m pytest -q tests/test_research_indexed_paired_ranking_dev.py
python -m scripts.research_indexed_paired_ranking_dev --mode validate \
  --out artifacts/research-indexed-paired-dev/validate.json
```

Only when a real pinned model is available and CPU dependencies are installed:
```bash
python -m scripts.research_indexed_paired_ranking_dev --mode real-e5-cpu \
  --out artifacts/research-indexed-paired-dev/pinned-e5.json
```

The second command reuses the **existing** pinned
`intfloat/multilingual-e5-small` (`fd1525a9fd15316a2d503bf26ab031a61d056e98`)
backend and validates that exact revision and CPU device before claiming a real
model was run. An injected fake/backend in unit tests is never labelled E5.

## Gates and known limitations

- Dedicated CI proves Python/Ruff/Pyright/no-model regression and frozen
  synthetic case counts. Model quality requires actually running the pinned
  backend, not assuming it from fixture tests.
- No independent publisher-authored tasks, broad multilingual translation
  coverage, external provider/tool execution, confidence intervals, response
  quality, agent success, production no-fit threshold, or semantic ranking
  quality for catalogs larger than 32 qualified routes is established here.
- Real E2 intake #1346, agent qualification #1477 and v0.18 release #1356
  remain separate and **HARD HOLD**. No default promotion or PR merge.

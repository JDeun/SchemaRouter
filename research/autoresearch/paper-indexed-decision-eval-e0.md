# Native direct-index bounded DecisionBackend + pinned E5 synthetic DEV

Scope: issue #1560, stacked after Draft #1749, date 2026-10-25. This is not a production ranker, model training, or independent E2.

## Why this work

Draft #1749 adds a source-complete semantic posting-index callback, only when 6–32 currently authorized original native field candidates remain. To compare a real ranker rather than a fabricated first-five, reuse the EXISTING decisions.DecisionRequest/DecisionOption/choose_sync envelope and existing pinned E5 CPU embedder.

The research adapter at scripts/research_indexed_decision_backend_ranker_e0.py accepts only bounded query text, eligible route IDs and source-visible required output field names. It never receives task gold, hidden fields, the registry, original provider schemas, source credentials, invokers, or arbitrary results. Its only output is a tuple of existing candidate offsets; incomplete/forged/duplicate choices fail closed. The enclosing native index independently checks every candidate, principal, policy, availability, and exact schema version again afterward. A 16,384-byte UTF-8 decision request cap protects model context. No execution authority is created.

## Paired synthetic DEV setup

scripts/research_indexed_e5_overflow_cpu_dev.py reuses the fixed 24 service route names and 27 supported (9 service tasks × EN/KO/JA) plus 3 OOD queries from the G5 experiment, but registers a distinct catalog of **input-free, direct** native source endpoints with exactly one typed service.status field. That makes this a direct FieldGroup retrieval test, **not** a G5 producer/consumer execution-path test.

Three conditions share a frozen source snapshot, original principal, identical typed FieldGroup and K=5: baseline >K abstention (no candidates), source-order first-five counterfactual, and optionally a source-authorized model Top-K5. Gold is used only by the offline scorer AFTER retrieval, never by the query carrier or model. Measures include EN/KO/JA Recall@5 counts, rescued vs regressed cases, OOD nonempty shortlist counts (not calibrated no-fit), and whole lookup p50/p95/p99/mean CPU-adjacent elapsed time. Tokens are deliberately reported unknown.

A library-injected decision backend is always UNATTESTED. Only the executable real-e5-cpu path loads the existing pinned intfloat/multilingual-e5-small revision fd1525a9fd15316a2d503bf26ab031a61d056e98 on CPU, checks it, and emits a report labeled REAL_PINNED_E5_CPU_DIRECT_INDEX_SYNTHETIC_DEV_ONLY with its actual Git SHA.

## Replay

- Adapter: scripts/research_indexed_decision_backend_ranker_e0.py
- Experiment: scripts/research_indexed_e5_overflow_cpu_dev.py
- Tests: tests/test_research_indexed_decision_backend_ranker_e0.py and tests/test_research_indexed_e5_overflow_cpu_dev.py
- GitHub Actions: .github/workflows/research-indexed-direct-e5-cpu-dev.yml
- Validate: python -m scripts.research_indexed_e5_overflow_cpu_dev --mode validate
- Actual CPU if runner provisioned: python -m scripts.research_indexed_e5_overflow_cpu_dev --mode real-e5-cpu --out artifacts/indexed-direct-dev/real-e5-report.json

## Strict research/release gates

No quality claim until a pinned real model report is visible from exact HEAD. Synthetic disclosed source IDs and developer-written cases are NOT independent. Source permissions, external maintainer-authored EN/KO/JA/OOD gold (#1346), same-principal externally executed agent task success (#1477), original Understand(q), >32 overflow and production-level tokens/p50/p95/p99 remain open. v0.18 release #1356 HARD HOLD and Draft PR state remain unchanged.

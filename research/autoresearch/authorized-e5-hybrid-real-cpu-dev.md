# Actual multilingual E5 model vs lexical vs hybrid on bounded CPU DEV

**Owner**: #1477 / #1339. **Not** independent E2, task-level agent
success, safety certification, calibrated no-fit, or product release.
**Hardware**: GitHub Actions Ubuntu 24.04, Python 3.12, CPU only.

## Why this actually runs a model

The prior #1481 bounded semantic bridge and #1483 source-authorized
RRF(60) hybrid selector are E0 code paths; earlier tests used only
`CallableDecisionBackend` fakes. This independent research runner
builds a real `EmbeddingDecisionBackend(E5CachedEmbedder(...))` backed
by an actual CPU `SentenceTransformer` encoder, with strict local
weights `intfloat/multilingual-e5-small` pinned to HF commit
`fd1525a9fd15316a2d503bf26ab031a61d056e98`, `trust_remote_code=False`.
The `E5CachedEmbedder` supplies correct asymmetric query/pass prefixes;
no provider API key or hosted inference is involved.

It reads the **existing, exposed 2026-10-15 synthetic DEV** corpus
`benchmarks/multilingual-embedding-cpu-dev-20261015.json`, verifies
its exact bytes and original data identity (84 cases, 13 source-native
read-only operations, 6 language groups of 8 supported + 6 unsupported
each). It explicitly does not create, rewrite, train on or select the
independent #432 task corpus.

All three arms use the **same** registry, `PrincipalContext` and
authorized scoped snapshot per query:

1. `lexical_k5`: current native `retrieve_authorized` K5.
2. `e5_k5`: the already implemented source-authorized, non-executable
   `AuthorizedFixed5DecisionSelector` driven by real E5 CPU vectors.
3. `hybrid_rrf60_k5`: the already implemented `AuthorizedHybridFixed5Selector`
   driven by the **same real model/backend** plus fixed RRF60 lexical.

This driver reports *retrieval* supported Recall@1/5, unsupported
**nonempty candidate shortlist** (not a native execution or calibrated
false accept), per-language denominators and p50/p95 CPU selection
latency. The E5 passage cache becomes warm through the task sequence;
the hybrid arm also does more work than lexical. This is descriptive,
not an end-to-end matched-agent token/success/latency or a robust
timing superiority claim. The backend output is always checked against
the original authorized source. No release / default promotion.

## Reproduction

```bash
python -m pip install "torch>=2.4,<3" --index-url https://download.pytorch.org/whl/cpu
python -m pip install ".[mcp]" "sentence-transformers>=5.1,<6" "transformers>=4.51,<5"
python -m scripts.evaluate_authorized_e5_hybrid_cpu_dev --mode validate
python -m scripts.evaluate_authorized_e5_hybrid_cpu_dev --mode real-e5-cpu \
  --output artifacts/authorized-e5-hybrid-dev/report.json
```

A dedicated Actions PR job **actually attempts** CPU inference and
uploads a versioned, source-pinned report. If upstream HF weights,
dependency resolution, or runner resources block the job, mark the
run `INFRA_INVALID` (not a scored failure or success), don't synthesize
model vectors or write a fake benchmark report. If E5 or Hybrid performs
worse on a language or unsupported cases, preserve the negative
result rather than tuning on this visible DEV dataset and rebranding
it confirmation.

**Next**: only an independently authored, publisher-reviewed native
source task cohort (#1346) with actual same-agent and host execution
(#1477 Milestone C) can support an E2/commercial agent-utility claim.
Frozen #432 is unchanged and v0.18 #1356 remains HARD HOLD.

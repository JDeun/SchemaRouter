# Joint candidate-pool and ranking optimization: Actions CPU only

Issue [#1412](https://github.com/JDeun/SchemaRouter/issues/1412).

The previous numeric optimizer reranked only the top 24 candidates returned by
the current `SchemaPlanner`. PR #1419's **measured**, previously exposed
synthetic DEV confirmed that required English routes sometimes sit outside
that pool even when in the top 64/128. Increasing pool size without
reordering did **not** improve achieved Top-5 routing.

## Reviewed v2 search grammar

The joint optimizer searches a **typed numeric/finite space**, not Python
source code:

- Real pool width: one of 24, 64, 128. Each is separately retrieved using
  the public current SchemaPlanner API and its registered typed registry.
- Five reviewed reranker weights: position, token overlap, trigram overlap,
  output-field vocabulary overlap, endpoint identifier overlap.
- Evolution uses seeded exploration, mutation, crossover, known prior
  research winner state. All candidate genomes and failed trials are
  accounted for.
- The fixed reference is the same current planner's **K24 top5** (identity
  weights). A champion can replace this research reference *only* if it
  improves required-route Top-5 recall while passing strict per-language,
  per-size, per-K non-regression on route count and multi-route full
  coverage. It must also meet fixed candidate p95, backend relative/absolute
  CPU p95 and candidate payload byte limits.
- Each experiment's back-end retrieval measurements are taken from a
  **preloaded cache of actual current SchemaPlanner calls** at all 3
  widths, 3 catalog sizes and 240 known task rows. Candidate ranking
  time is measured separately per trial. Retrieval p95 statistics are
  based on preloaded trials; they are not separate per-genome cold-cache
  retrieval. Do not interpret p95 as real user-request latency.
- Only search *fit* results can propose a candidate; the other internal
  *check* split is evaluated when candidates pass fit gates. Since all
  samples were previously exposed and derived from **the same generator**,
  this check is **not independent or blinded**, and repeated adaptive
  selection can overfit it. No agent completion metric is available.

## Event-driven lifecycle

A reviewed first merge to `main` starts the workflow through a filtered
`push`. There is **no Cron**. A manual workflow_dispatch can also start a
new research chain. A successful run writes exact source/corpus-hash-bound
`state.json` and `report.json` to GitHub Actions artifacts **before**
a minimal separate job, which alone has `actions:write`, requests the
next run via explicit `workflow_dispatch`. The next CPU job, with only
`contents:read` and `actions:read`, validates and downloads that exact
previous run's saved state; no silent fresh-start substitution.

A chain is capped at **eight batches**, with at most **12 numeric trial
configurations per batch** (96 upper bound), or stops earlier if there is no
new candidate, a failure or a source/identity/budget mismatch. GitHub may
queue a run. An intentionally new source revision invalidates saved
genomes rather than mixing incomparable results.

This workflow is separate from the existing version-one search chain, so
no in-progress v1 run loses its expected manifest or source identity.

## Reproduce on a disposable Actions Linux CPU checkout

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_actions_joint_pool.py
python -m scripts.research_actions_joint_pool \
  --trials 2 --seconds 180 --remaining 8 \
  --output-dir artifacts/joint-cpu-dev
```

## Unresolved limitations

- All corpus results refer to the previously exposed *synthetic*
  multilingual #430 generated DEV tasks, not authentic heterogeneous
  OpenAPI/MCP/DB/Vector/Graph deployments or independent benchmark gold.
- Model-independent tool candidate ranking cannot decide the user's intent
  or grant host principal RBAC/ABAC policy, cannot guarantee no-fit, and
  does not evaluate required output-field selection or actual agent task
  success.
- The hypothetical gold-informed pool ceiling from #1419 is **not used as
  an input feature or claimed as achieved accuracy**.
- A missing route even at K128 still cannot be recovered by this search
  grammar. Fixing candidate generation and adding real-schema training/
  development sets require reviewed product/benchmark code, not an
  unsandboxed source-writing agent.
- This research winner is **never auto-merged** into product code and
  never qualifies v0.18, which remains HOLD behind its independent
  evidence gate. Historical independent negative results are unchanged.

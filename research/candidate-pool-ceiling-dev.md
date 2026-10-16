# Current API candidate pool ceiling — visible multilingual DEV

Issue: [#1412](https://github.com/JDeun/SchemaRouter/issues/1412)

**Why this instrument matters:** The current GitHub Actions-only adaptive research
search mutates five reviewed weights to rerank *only* the original 24
`SchemaPlanner.retrieve` candidates. If the required route is absent from
that pool, no ranking configuration can recover it. The correct next
architectural choice depends on measuring whether poor Top-5 exposure is
caused by a narrow candidate pool or by bad ordering *inside* the pool.

## A source-bound experiment, not a performance qualification

The runner `scripts/research_candidate_pool_ceiling_dev.py` invokes the
actual current public `SchemaPlanner.retrieve` with `k=24,64,128` for
the **same query**, under the same **registered 100/250/500 synthetic
catalog**. It measures actual ranked Top-5 found-route and
FullCoverage@5, the fraction of necessary registered routes present
*anywhere* in each pool, and a separately labeled hypothetical
**gold-informed Top-5 ceiling**: the best score a perfect reranker could
achieve *if told the gold route IDs*.

That oracle is not an actual product condition, is never supplied as
input to the planner or ranker, and must not be confused with an
achieved Top-5 Recall or real downstream agent success. A hypothetical
ceiling can be high when every actual ranker still fails.

All query rows come from the *already exposed generated #430 DEV* (six
languages, eight strata, 240 existing queries per catalog; balanced PR
smoke uses 48/case size). No external hidden gold, historical #432
holdout, actual principal permissions, required output-field gold,
live provider integrations or tool execution is accessed. Neither a
candidate shortlist on an unsupported query nor a higher oracle ceiling
implies authorization, no-match calibration or successful agent tasks.

Source SHA-256, current checkout commit, raw missing route IDs, observed
ranked route IDs, K-sensitive candidate prefix changes and request CPU
timings are retained as a JSON artifact. Each width is **separately
executed and timed**, not approximated by truncating the K128 call.
Like other PR smoke, request p95 is not statistically stable.

## Reproduce without additional compute infrastructure

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_candidate_pool_ceiling_dev.py
python -m scripts.research_candidate_pool_ceiling_dev \
  --cases-per-group 1 \
  --output artifacts/candidate-pool-ceiling-dev/report.json
```

The workflow runs exclusively on GitHub Actions Linux CPU, uses read-only
credentials and creates no product code changes or releases.

## Decision rule for the next reviewed optimizer family

1. If required routes are absent at K24 but present at K64/K128, add a
   separately reviewed **adaptive pool-width** strategy (with costs
   observed and provenance), then let the Actions-only optimizer search
   the registered width and ranking parameters. The existing auto-search
   loop cannot widen its pool by changing ranking weights.
2. If relevant routes are present at K24 but not in Top-5, prioritize
   field/operation-aware reranking, *without* exposing gold labels to
   candidate code.
3. If required routes are absent even at K128, widening alone may be
   insufficient: candidate generation/typed indexing and genuine
   multilingual semantic retrieval require their own reviewed adapters.
4. All DEV conclusions are provisional. Final product success still
   requires genuine new current-adapter, query-disjoint evaluation with
   per-principal eligibility, required-field gold and actual downstream
   fixed-agent FULL/SR-K/SR-PROGRESSIVE/ORACLE task outcomes.

The main research chain remains an isolated finite Actions-only,
artifact-resuming numeric optimizer; this diagnostic does not change
its frozen search contract mid-chain. Original v0.18 release gate is HOLD.

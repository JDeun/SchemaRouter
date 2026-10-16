# V3 finite Actions-only multiwidth adaptive research

Parent [#1412](https://github.com/JDeun/SchemaRouter/issues/1412).

The first completion-triggered research chain successfully ran 12 batches
and 275 configurations without an external coding agent or model API.
It could modify only weights of a fixed top-24 ranker.

The measured full exposed DEV matched-cohort studies show:

- Frozen final V1 K24: 607/630 required routes at Top5 (96.35%).
- Frozen V2 K64: 618/630 (98.10%), but its 1.54× CPU p95
  **failed** our existing strict 1.50× cost constraint.
- Reviewed width-interpolation V3 K56 with V2 weights:
  617/630 (+10 vs V1) at 1.43× CPU p95 in one Actions run.
  This study is also on the SAME known synthetic generator and
  should not be confused with independent task performance.

The new `scripts/research_v3_actions_search.py` creates and mutates
**only** numeric candidate genes among registered widths
`24,32,40,48,56,64` and the existing five reviewed lexical, trigram,
field, identifier and positional weights. It performs actual current
`SchemaPlanner.retrieve()` calls for every width against the
100/250/500 registered synthetic DEV catalogs. It enforces paired
K3/K5/K10 nonregression **per language and catalog**, required
multi-tool FullCoverage, serialized schema byte cost, 20ms ranker
CPU p95, 150ms absolute request p95, and **1.50×** request CPU p95
relative to the frozen final V1 K24 incumbent.

The source and benchmark/scorer/workflow hashes are sealed in each
artifactual state. Per-batch DEV train/check uses distinct task rows
of the **same exposed generator**; this is not external independent
confirmation. Candidates never receive gold labels or create new
tool permissions. Unsuccessful configurations are preserved.

## Finite completion-triggered operation

After the reviewed workflow file lands in protected `main`, one
filtered push starts the initial study; a manual
`workflow_dispatch` can also start a new bounded chain.
Research jobs are read-only (`contents:read`, `actions:read`).
After report and source-bound state upload, a **separate** minimal
job with only `actions:write` starts the next workflow_dispatch,
passing its predecessor run ID and one less remaining budget.
The next job retrieves exactly that predecessor artifact and checks
the workflow identity, main branch, source commit, source/DEV
hashes, allowed candidate genome and current epoch.

**Hard run limit:** at most **6 batches of 12 configurations**
(72 attempted configurations; fewer if duplicates/no novelty).
There is no Cron, unlimited loop, external computer, coding agent,
GPU, paid model API, product write permission or automatically
enabled release. An expired artifact, changed main source SHA,
failed evaluation or unrecognized state stops the chain.
GitHub Actions runner queues may delay the next run.

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_v3_actions_search.py
python -m scripts.research_v3_actions_search \
  --trials 3 --cases-per-group 2 --remaining 6 \
  --output-dir artifacts/v3-width-search
```

This is **only an optimizer research subsystem**. A successful
synthetic DEV champion is not evidence of real-source independent
qualification or downstream LLM-agent task success. The separately
authored current OpenAPI/MCP/typed field/permission DEV is only
local protocol-shaped data; authentic current provider and fixed
agent comparisons remain prerequisites for any production rollout.
v0.18 release #1345/#1346 stays HOLD.

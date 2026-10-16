# Joint candidate breadth and reranking search (V2 DEV)

Issue: [#1412](https://github.com/JDeun/SchemaRouter/issues/1412).

This is the **next reviewed algorithm family** for a GitHub Actions
Linux CPU-only research environment. The existing V1 event-driven
12-batch chain remains untouched until terminal. V2 is an isolated
proposal/test, **not yet an event-driven replacement**.

## Reason for the new family

The existing optimizer is limited to a top-24 registered capability
pool. A real current-public-API DEV diagnostic, [#1419](https://github.com/JDeun/SchemaRouter/pull/1419),
on 500 synthetic endpoints found EN Top-5 route recall 74.3% for
all pool widths 24/64/128, while its hypothetical gold-informed ceiling
was respectively 88.6%, 94.3%, and 97.1%. These ceilings are **not**
achieved performance and are from the same pre-exposed synthetic
#430 data generator.

V2 may *jointly* change the retrieved **pool width** (24,64,128)
and the already reviewed five ranking-feature weights (position,
token overlap, Unicode character trigrams, output-field words and
route identifiers). It cannot change registered routes, schema,
principal rules, validated plan/execution logic or raw queries.

## Measured experiment

`scripts/research_actions_width_search_dev.py` first calls the
**current `SchemaPlanner.retrieve(k=24/64/128)` separately** on the
same actual registered catalog, recording the true retrieval latency
for each width. For every generated configuration it reranks only
metadata from that width's registered candidate list; it cannot use
task gold as a feature or invent candidate IDs.

Scores are paired against the current K24 ordering at K3/K5/K10:
required-route count, AllRequired FullCoverage, actual materialized
candidate JSON bytes, pure ranking p95, and registered retrieval
plus ranking request p95. The existing strict `decide()` guard
requires positive supported Top-5 found-route gain and zero per
language/size/K coverage regression. V2 adds an actual request p95
ceiling of 150ms, which is a conservative **experimental budget**,
not a production service-level guarantee.

The first three tested controls explicitly use K24, K64, K128 with
identical base ranking. Remaining candidates derive from safe
mutation of reviewed weights and width choices. The best result
is retained as a **research-only** champion after internal-check
pass; negative attempts are not hidden.

The 6 languages × 8 strata × 100/250/500 benchmark comes from the
previously known #430 generated DEV. The default job splits two
distinct task rows per language/stratum into one fit and one internal
check row. Optional full visible DEV uses three fit and two check
rows per stratum. Neither is independent confirmation, real
provider protocol generalization, a security audit, field recall
gold, or actual agent answer/task success. It is possible that
**no candidate passes** the restrictive gates; that is a legitimate
result and must not be fabricated into progress.

## Reproduce with GitHub Actions CPU

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_actions_width_search_dev.py
python -m scripts.research_actions_width_search_dev \
  --trials 9 --cases-per-group 2 --seed 1412 \
  --output artifacts/width-aware-research/report.json
```

Workflow `research-pool-width-optimizer-dev.yml` is read-only and
runs only in PR/manual contexts. A separate review is required
before adding this broader operator to the ongoing event-driven
V1 Actions chain; changing its source hash mid-chain would
intentionally invalidate resume state.

Future prerequisites: freshly authored real current-adapter
OpenAPI/MCP/vector/graph/database cohorts, per-principal eligible
route and required output-field labels, non-overlapping
independent confirmation, and fixed-agent FULL/SR-K/
SR-PROGRESSIVE/ORACLE task outcomes. v0.18 #1345/#1346 remains HOLD.

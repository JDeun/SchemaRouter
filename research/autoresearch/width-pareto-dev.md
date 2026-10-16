# Width Pareto: preserve V2 accuracy without violating V1 CPU budget

Parent: [#1412](https://github.com/JDeun/SchemaRouter/issues/1412).

The exact [V1-vs-V2 paired CPU study #1423](https://github.com/JDeun/SchemaRouter/pull/1423)
was completed on all 720 pre-exposed synthetic DEV requests in GitHub
Actions. Frozen final V1 (top-24 reranker) recalled **607/630** required
routes at Top-5; frozen V2 (top-64 reranker) recalled **618/630**
(+11) without a language/catalog/K group regression. V2's measured
CPU retrieval+ranking p95 was **26.601ms** vs V1 **17.269ms**, or
**1.54×** the incumbent, missing the deliberately set **1.5×** cost
limit. The existing strict paired ranking/byte guard passed; only
the additional measured relative CPU limit failed. This is a
research diagnostic, not a deployment acceptance test.

To find the cheapest pool retaining true *observed* V2 improvements,
this study calls the **current public SchemaPlanner.retrieve** at
each reviewed width **24, 32, 40, 48, 56, 64** on exactly the same
100/250/500-route catalogs and EN/KO/JA/ES/DE/mixed DEV requests.
Every K retrieves and times its own actual candidates: it is
not an approximation obtained by truncating a wide response.

The fixed frozen V2 reranking weights are applied to each width's
registered candidate metadata; the frozen final V1 incumbent is
evaluated at K24 on exactly the same requests and physical Linux
runner. The existing reviewed scoring and no-regression guard
operates at K3/5/10 per catalog/language, plus paired selected
metadata bytes and rank CPU p95. This study adds a **hard**
request-level p95 criterion of <=1.5× V1 and <=150ms absolute.
We record all misses, regressions and failures. A research
candidate qualifies only if **all** strict DEV criteria pass.

No gold routes can enter the ranking function; a candidate can
only permute the IDs already returned by registered current
retrieval and cannot authorize, invoke or plan execution.

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_v3_width_pareto_cpu_dev.py
python -m scripts.research_v3_width_pareto_cpu_dev \
  --cases-per-group 5 --output artifacts/width-pareto-cpu-dev/report.json
```

## Interpretation constraints

This is **retrospective re-evaluation on an already exposed
synthetic DEV generator**. Both original configurations were tuned
against that generator, and width selection now sees it yet again;
the pool sweep itself compounds selection bias. A nominal pass can
only identify a promising **reviewed search grammar candidate**
for a future new independent test. It must not cause automatic
promotion, v0.18 release, or optimistic commercial claims.

The CPU p95 measured on one GitHub runner is environment-dependent,
including due to caching and runner contention; retest under pinned
multiple-run conditions before operational rollout. Neither
real third-party provider requests, authenticated principal/field
gold, nor downstream agent task completion is measured here.

The V1 completion-triggered 12-batch self-search is finished;
the V2 source is research-only. This workflow runs on PR/manual
Actions CPU and **does not silently create a new unbounded chain**.
The release HOLD remains in place.

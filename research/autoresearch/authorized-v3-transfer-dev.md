# V3 ranking transfer on a new handwritten principal/field local DEV

This experiment is intentionally separate from the exposed #430
synthetic 720-request sweep on which the weights were previously tuned.
It uses 27 manually authored EN/KO/JA cases, one local OpenAPI 3.1
document, one local MCP `tools/list`, and three native typed
SQL/vector/graph contracts from the review-gated #1422 DEV fixture.

It calls the actual current `SchemaRouter.retrieve_authorized()`
with a synthetic trusted host principal and deny-by-default policy,
then reorders **only the principal-authorized returned route IDs**
with frozen V1 vs frozen V2 weights (V3 K56 proposal). The evaluator
independently checks eligible routes and required declared output
fields, records every language/role case and refuses to equate
non-empty retrieval for unsupported queries with execution approval.

**Important geometry:** this local catalog has only **10 endpoints**,
fewer than both K24 and K56. Thus changing the pool width has
**no effect on which registered candidates are initially available**.
This study tests the generalization of the **reranking weights**
under current authorization and field metadata; it **cannot**
confirm the widened K56 candidate generation mechanism or its
large-catalog CPU performance.

No external vendor is contacted; parser fixtures are local and
manually authored after the V1/V2 search evidence was available,
not a blind or independent benchmark. No real authenticated host
identity, data-record scope, downstream agent task completion,
external execution or v0.18 acceptance can be inferred.

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_v3_authorized_adapter_transfer_dev.py
python -m scripts.research_v3_authorized_adapter_transfer_dev \
  --output artifacts/authorized-v3-transfer-dev/report.json
```

GitHub Actions Ubuntu CPU is the only compute environment used.
The workflow has `contents:read` and does not write product source,
start an autonomous job chain, call remote tools or promote new
ranking weights. All results are diagnostic. The release HOLD stands.

# E1: declared complete FieldGroup eligibility BEFORE principal-scoped Top-K

Issue [#1535](https://github.com/JDeun/SchemaRouter/issues/1535); original
[SchemaRouter paper](https://arxiv.org/abs/2608.21375) Algorithm 1 and
[#1530](https://github.com/JDeun/SchemaRouter/issues/1530) parity audit.

## Gap in the current default

The native planner rewards individual exact fields by +6, lexical by +3,
substring by +1. Any positive relevance can enter K5. Therefore when a
trusted request requires **both** semantic fields A and B, an A-only route
can be returned as a *relevant candidate* even though it cannot answer the
full requirement. This is neither a completed field group match nor a
validated multi-hop plan.

## Strict E1 experimental condition (not product default)

`scripts/research_required_field_group_e1.py` models an explicitly
host-declared **conjunctive** `DeclaredRequiredFieldGroup` alias-to-field
edge (EN/KO/JA exact aliases, 1–8 distinct typed semantic IDs). It composes
the existing `SchemaRouter` authorization predicate, principal-scoped
analysis registry, `_data_scope_endpoint_view` field projection and
`SchemaPlanner.retrieve_with_scoped_schema`.

**Before** native candidate sorting and K=5 clipping, each candidate
must provide **every** required semantic field within the **same currently
visible endpoint**, with compatible required datatype, exact declared
unit, all required qualifiers and optional exact source-type/license labels.
A hidden field, denied endpoint, different unit, insufficient source
declaration or partial field match is **not** an eligible positive.
A source fingerprint/version/permission witness is checked around disclosure;
there is no extra invoke/plan action or host authority grant.

The test includes a baseline native `retrieve_authorized` result that can
include a partial route, then demonstrates the gated condition discloses
only the complete/typed/authorized route. The tests do **not** alter default
ranker scoring or reinterpret its existing Top-K metrics.

### Interpret results correctly

This only proves an opt-in **single-endpoint group** path on synthetic
declared contracts. Split A/B among two tools is **NOT** supported merely
because their union covers the set. That needs verified producer/consumer
edges, join identifiers, dataflow evidence, budgets and real independent
multi-hop tasks; no such capacity is inferred here. An empty result is
**not** independently calibrated no-fit. Matching `license` is metadata
comparison, **not** legal clearance or provider permission. No translation
is inferred from string similarity. The explicit alias list is not
independent multilingual test data.

### Promotion decision

A production graph/field-group router requires [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)
external publisher-authored, independently reviewed source/task gold,
joint EN/KO/JA route **and required field-set** recall, unsupported
false acceptance/refusal, same-authority comparison to native lexical
K5, source drift and deep/nested-hidden-field attacks, warm Linux CPU
p50/p95/p99, real model schema tokens, and [#1477](https://github.com/JDeun/SchemaRouter/issues/1477)
actual external-agent task completion. Do not change frozen #432,
production defaults, or v0.18 [#1356](https://github.com/JDeun/SchemaRouter/pull/1356)
HARD HOLD on synthetic E1 evidence.

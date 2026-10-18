# E0 synthetic byte-cost diagnostic for agent-neutral tool catalog (#1477)

## Objective and scientific boundary

Compare two **non-equivalent** agent-visible disclosure shapes using the same
current authorized registered source in an isolated host-only test:

- A **full currently authorized catalog index** of registered route IDs and
  descriptions, followed by a selected route's detailed schema.
- The **selected five schemas alone**, without a full catalog index.

These are **UTF-8 serialized JSON byte counts**, *not* measured tokenizer
counts, actual prompt lengths, model context savings, exact model route recall
or agent task success. The index can cost **more**, not less, than five
fully materialized definitions, especially at 500 tools. The index pathway
also changes the model's selection process and cannot be counted as an
equal-K task-success benchmark without a separate paired agent study.

## Exact synthetic sources and controls

Use the existing local `build_fixture` with exactly 100/250/500 mixed
OpenAPI/MCP/DB/vector/graph endpoint routes and viewer/editor principal
policies. Query stays constant and never appears in public output.
The code reuses the #1527 `AuthorizedAgentToolSurface.catalog_index()`
capture, auth witness, output field scope and maximum serialized-byte cap.
For each source/role pair count only numbers, a fixed synthetic role name
and coarse status; do not write route IDs, descriptions, raw model prompts,
backend traces, gold labels, provider results or credentials.

- Strict tool-definition selection remains first five **visible** source
  routes, K=5; no gold-aware picks or filling omitted index entries.
- An index larger than the default **32KiB** is reported as
  `rejected_oversize_complete_catalog` with `index_bytes: null`, not a
  successful/truncated catalog. The 128KiB host hard ceiling is unchanged.
- Counts are permission-scoped; 100/250/500 describe *physical synthetic*
  catalog sizes, not number of visible routes for a principal.
- Neither `SchemaRouter.plan`, `execute`, an LLM, a network client nor
  an invoker is used. No tool selection quality/semantic benchmark is run.
- `index_plus_one_detail_bytes` combines the full index and **one**
  selected detailed schema and is *not* an apples-to-apples improvement
  percentage versus five schemas alone.

## Decision boundary

Only observe whether the complete two-stage index can fit the configured
byte budget and its additive context cost. Do not promote as a faster/cheaper
product API or multilingual retrieval fix from these synthetic observations.
The original frozen #432 negatives, publisher-authored #1346 E2 hold, and
v0.18 #1356 release hold remain unchanged.

For real product qualification: preregister equal-authority, equal source
revisions and budgets, paired task-level success, EN/KO/JA no-fit and
security, tokenization for the chosen agent and CPU p50/p95/p99. This E0
report supplies only a cost input into that future decision.

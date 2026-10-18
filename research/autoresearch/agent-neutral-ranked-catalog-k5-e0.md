# E0: query-ranked K5 catalog preview (agent-neutral) (#1477)

## Trigger

Real synthetic observation in PR #1528 / Actions #39101288441:
the **complete** authorized catalog index costs 5,308 / 13,588 /
27,388 UTF-8 JSON bytes at 100/250/500 physical routes for Viewer,
compared with 1,347 bytes for the five selected tool definitions.
The fully authorized 500-route Editor index exceeds the research-only
32KiB cap and correctly fails closed. A raw full-catalog publication
does not offer a scalable agent-facing default. These are disclosed
synthetic bytes, not measured LLM tokens or equal-task outcomes.

## Bounded correction

New `AuthorizedAgentToolSurface.ranked_catalog_preview(k=5)` on the
**scripts-only** view returns the first `k` currently authorized,
query-ranked original-source route IDs and public descriptions already
captured by `retrieve_authorized(query, principal, k=physical)`.
Only K visible entries are encoded, so even if the full 500-route
authorized index is over budget, this query-specific preview can be
disclosed. It does **not** fetch, independently decide, call or plan.
No independent semantic reranker, LLM, API, provider code, hidden
source count or callback authority is introduced.

The application/agent next selects one of those advertised IDs; if it
chooses to act, the trusted host calls existing `tool_definitions([id],
k=1)` for typed arguments, and execution continues to require the
existing independent authorized host validation. An empty result is
NOT a reliable unsupported/no-fit judgment.

## Safety and experiment scope

- Never use the full physical catalog as model context merely to rank;
  that is the router's internal source and is not the model's inventory.
- Native output fields, descriptions and identity must have passed the
  existing principal/data-scope/availability checks. Every disclosure
  checks current source, principal and authorization integrity.
- Valid `k` is 1..5, bool and non-integers rejected. No silent
  fallback to more routes when lookup fails; oversize K5 fails closed.
- The index preview does not grant a tool-call capability. The model
  still chooses the tool and its arguments; router cannot run an agent
  loop or produce task answers.
- Synthetic 100/250/500 adapter-scale regression, immutable
  source/integrity, viewer/editor permissions, forged mutations,
  denied-route and hidden-field canary and zero plan/execute tests.
- No product API, default retrieval ranking, released behavior,
  frozen #432 results, independent E2 source/gold or v0.18 release
  gate is changed.

Next step: measured token/cost and agent retrieval/final-task paired
results on *independent publisher-disjoint* #1346 sources. Do not
promote the K5 preview from E0 from only synthetic assertions.

# E0: agent-neutral principal-scoped catalog index (#1477)

## Product boundary

SchemaRouter is an **agent-facing capability catalog and typed contract
boundary**, not an autonomous agent. The host/agent decides whether to call a
tool, which candidate ID to select, arguments, follow-up calls, and the final
answer. A retrieved candidate is never an execution grant. If the host
**explicitly** invokes the router's planner/executor, it must re-check
authority, schema, binding and output projection.

This research slice adds `AuthorizedAgentToolSurface.catalog_index()` to the
existing opt-in **scripts** layer only. There is no change to public
`SchemaRouter.retrieve[_authorized]`, model selection, default ranking,
`plan/execute`, tool invokers, frozen #432, release packaging or model loops.

## Two-stage disclosure flow

1. Trusted host captures the current authorization-visible registered routes
   through `capture_authorized_agent_tool_surface(router, query,
   principal=...)`. Retrieval, data-scope, policy and availability checks
   happen here as before.
2. `view.catalog_index()` emits an immutable tuple of **route ID, source-safe
   short description**, in currently authorized source order. It does not
   include callable objects, credentials, executable plans, raw provider data,
   tool argument schemas or a hidden source count.
3. The agent/application selects a route ID; the host requests
   `view.tool_definitions([selected_route], k=1)` for its full projected
   argument schema, or a bounded selection of up to five definitions.
4. The host separately chooses whether to validate/execute that tool. Showing
   a definition cannot trigger network traffic or mutate source data.

Both views use the **same capture and source-integrity receipts**; every
disclosure checks for changed registry/policy/principal/source descriptions
before and after constructing the value. Index JSON is bounded by UTF-8 byte
count (32 KiB default, hard ceiling 128 KiB), rejects oversized catalogs
instead of silently hiding entries, and exposes no no-fit verdict. Empty
visible catalog is NOT an independently calibrated unsupported/no-fit outcome.

## Evaluation status / acceptance

This is E0 engineering, **not** a full-task agent benchmark or a multilingual
accuracy improvement. Unit tests use in-process synthetic tools and principal
policies and assert hidden descriptions/fields and denied routes stay hidden,
selection is two-stage and nonexecuting, output is immutable, byte budget
is enforced, authority drift fails closed, and empty visible catalog is
not treated as known unsupported. Existing fixed-K callback and frozen
benchmarks are untouched.

Next scientifically meaningful qualification under #1477/#1339/#1346:
compare *measured* agent-visible token cost and independent EN/KO/JA full-task
completion under the same strict K, valid publisher-authored task/gold, and
source authority. No #432 reinterpretation, no v0.18 release promotion.

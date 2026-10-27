# Algorithm 1 P2 direct host-argument wiring — 2026-10-27

Issue #1560; continuation on the unmerged #1755 research stack.

## Missing behavior

The original G5 typed ToolCall compiler accepts an exact host-approved
scalar root argument, and the graph compiler accepts it for producer roots.
The structured Understand **direct** compiler and scoped A5 bridge do not
forward such a value, even when the original index explicitly approves that
route as a host root. This leaves a valid direct source route perpetually
`requires_arguments`; model `parameter_hints` must remain untrusted.

## Chosen approach

1. Reuse `_compile_one_route` and `_check_current_call_scopes` rather than
   creating a second argument validator. Add optional `host_source_arguments`
   to the direct compiler and limit it to already proven routes; recheck
   values and original source/policy after the second proof. Reject partial,
   unknown, non-host-root, malformed and unapproved input declarations.
2. In the named graph compiler, forward host inputs **only** when they name a
   fully proved direct route. Otherwise retain the current graph-root route
   behavior; never prebind a consumer or invent model values.
3. Forward a separate host-owned argument mapping through opt-in scoped A5
   planning/episode entrypoints, pinning it across the awaited model call.
   No query-text extraction, source execution, policy promotion or default
   ranking change.

## Evidence and tests

- RED→GREEN: owner-approved root scalar changes direct receipt to `ready`,
  while model hints alone still leave `requires_arguments`.
- RED→GREEN: named-graph direct path uses same trusted scalar; real G5
  producer-root path remains unchanged, with original current source proof.
- RED→GREEN: wrong route, missing/extra keys, hidden scoped limit, source
  changes and mutation across the model callback fail closed. During review,
  an availability callback also mutated the host input between the first
  named-graph direct probe and final binding: a separate observed RED→GREEN
  regression now prevents this intermediate swap.
- Run affected suites, Ruff, broader tests, then record exact local branch
  and any remote CI separately. Do not call E0 independent E2.

## Considered alternatives

- Parse DOI/IDs automatically from the query or trust a model parameter
  hint: rejected because the LLM does not grant input-binding authority.
- Change the default lexical planner or execute a direct receipt inside
  this code path: rejected; would bypass existing staged qualification and
  explicit separate host execution.

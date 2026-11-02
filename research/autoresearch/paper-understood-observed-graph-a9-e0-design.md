# A9 E0 — Source-Proven Named Graph Observation and Execution

## Scope and boundary

Connect the existing opt-in `compile_paper_understood_graph_plan` 1-/2-hop
typed DAG to real tool observations. This is **not** Algorithm 1 independent
E2, provider identity verification, a new autonomous agent loop, or default
routing. Keep Draft #1755 and release #1356 on hold.

## Decision

- Use the current original G5 named-graph compiler as the sole path/edge
  authority. Recompile the **same complete path** before/after each await and
  before/after binding. Do not independently infer a new one-hop edge from
  intermediate outputs, or expand a ranked/unverified graph.
- Accept only caller-supplied, **explicit approved host-root** scalar inputs;
  never copy the model's `parameter_hints` into a `ToolCall`.
- For every edge, reconstruct the original G5 one-hop validation shape from
  the pinned complete named DAG, then reuse
  `_materialize_original_observed_edge` for projected scalar/source/schema
  checks. This internal reconstruction is never offered as a public proof;
  current complete DAG equality is mandatory before and after.
- Invoke each read-only node **once** with `SchemaRouter.execute`, via a
  separate `ExecutionPlan` and `ExecutionBudget(1,1,1)`; there is no other
  tool invocation path, retries, or asynchronous parallel execution.
- Pin principal claims, owner intent/catalog, model suggestion and host inputs
  across each awaited tool operation; refuse drift in source, policy, scope,
  schema, value, route or authorized output projection. No partial receipt.
- Return observed `ToolResult`s and bound typed DAG only on total success.
  The receipt explicitly has `provider_provenance_verified=False`,
  `executable_authority=False`, and `independent_e2=False`.

## Negative cases

No named target; missing/forged/unapproved root arguments; wrong, null,
non-scalar, non-finite or absent observed ID; wrong executor result identity;
revoked middle/target; mutation during root/middle/target I/O; model target
unavailable; more than two edges; transient invocation must not retry.

## Completion boundary

A9 E0 can be marked as a **bounded source-proven local execution slice** only
after RED/GREEN tests, targeted regressions, Ruff/Pyright and exact remote
CI. The broader A9 item stays unchecked until agent-triggered provenance and
independent/source-attested behavior are demonstrated beyond this local API.

## Next vertical slice: actual captured Understand → bounded DAG executor

Connect the existing one-shot `analyze_paper_understanding_scoped` model
callback (which exposes only a captured authorized route menu) to the A9
original G5 executor bridge. The host must see the **same** captured visible
routes as the selected DAG before invoking a producer. An empty scoped menu,
unrecognized tool, ambiguous/unproved DAG or missing approved source-root
input makes zero registered executor calls. This opt-in wrapper is **not** a
replacement for the existing fixed5 agent episode, does not synthesize an
answer, and does not promote graph calls to a general model-controlled loop.

# 0.14 execution-state-aware corrective re-retrieval

Tracking issue: #431

This experiment asks whether a multi-step agent can recover missing next-step capabilities by
re-retrieving from **observable typed execution state**, rather than only widening the candidate
list generated from the original query.

#423 B2 is terminal, so the experiment is now authorized through the automated #500 conveyor.

As of 2026-10-02, recovery run `36897645512` is executing the unchanged frozen scientific source
`30663de8f618bc88a893d9bf6214035a70e8e894`. Earlier wrapper/cache failures are infrastructure
evidence only. No partial shard outcome may be interpreted, tuned against, or promoted before the
terminal aggregate and preregistered gate are available.

## Prior art

This protocol is independently motivated by two 2026 results:

- Patel et al., *Dynamic Tool Dependency Retrieval for Lightweight Function Calling*
  (Findings ACL 2026), which conditions retrieval on the initial query plus evolving tool-calling
  state/dependencies.
- Fang and Glass, *Beyond Single-Shot: Multi-step Tool Retrieval via Query Planning*
  (Findings ACL 2026), which replaces one-shot matching with iterative retrieval queries for
  compositional tool use.

SchemaRouter's experiment is narrower: it permits only observable typed execution
state, never hidden future routes, oracle task graphs, or retrieval-derived execution authority.

## Frozen state contract

The research retriever may condition on:

- the original user query;
- already executed registered route IDs;
- observed field names;
- observed semantic IDs;
- observed value types;
- units, dimensions, and qualifiers;
- stable identifiers produced by completed tools;
- the last execution status;
- the last error class;
- a deterministic task-incomplete boolean.

The state is serialized as canonical sorted-key JSON and appended to the original query only for the
research retrieval call.

The following are forbidden:

- future required route IDs;
- gold next-route IDs;
- oracle task graphs;
- hidden expected answers;
- hidden reference facts;
- condition names;
- SchemaRouter rank scores or rank positions.

Free-text tool output is not injected into retrieval context.

## Frozen conditions

Compare:

1. SR-5-STATIC;
2. SR-PROGRESSIVE-STATIC;
3. SR-5-STATE-AWARE;
4. FULL;
5. ORACLE.

The state-aware condition starts with Top-5 and may refresh at most once after each completed or
failed tool turn, with at most five retrieval refreshes per episode. Each refresh exposes at most
five capabilities.

## Surface

The frozen evaluation surface contains **180 independent semantic tasks**:

- 5 multi-step/state strata;
- 6 languages;
- 6 tasks per stratum × language cell.

Strata:

1. two-step state dependency;
2. three-step state dependency;
3. recoverable execution failure;
4. identifier/provenance propagation;
5. typed unit state transition.

Catalog sizes are 100, 250, and 500 endpoints.

## Primary metrics

Report separately:

- deterministic task pass;
- next-required-tool Recall@5 after each observable state transition;
- recovery rate after an initial miss;
- multi-step state completion;
- total unique candidates exposed;
- tool-schema and total input tokens;
- retrieval calls;
- model turns and tool calls;
- wall latency;
- failed executions;
- unauthorized destructive executions.

## Success gate

State-aware corrective retrieval is useful only if:

- task pass is no worse than static progressive by more than 2pp;
- next-required-tool Recall@5 is at least 97%;
- initial-miss recovery is better than static progressive;
- mean tool-schema tokens are lower than static progressive;
- unauthorized destructive executions remain zero;
- execution-policy integrity remains 100%.

The primary interval is a stratified task-cluster bootstrap over task-stratum × language with
10,000 iterations and seed 20260929.

## Boundary

Dynamic retrieval changes candidate exposure only. It cannot authorize execution.

No rule may be tuned from B2 failures, and no state field may be added after scoring begins.

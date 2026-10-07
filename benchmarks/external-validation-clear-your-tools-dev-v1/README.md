# Clear Your Tools external-validation execution contract

Status: **development protocol — not scored evidence**

This package prepares issue #839 without selecting a winner or tuning on held-out outcomes.

## Frozen comparison strata

The primary end-to-end comparison keeps the agent, model, catalog, tasks, prompts, backend state,
timeouts, and scoring fixed while changing only the tool-selection/context layer:

1. full-catalog baseline;
2. Clear Your Tools (CYT) native proxy/hook;
3. SchemaRouter native typed capability routing.

Secondary CYT modes are pre-registered separately: English BM25, English LLM pruning, English
reranker, Korean LLM pruning, and Korean reranker. Korean BM25 is intentionally excluded.

## State regimes

Never aggregate these regimes:

- `cold_start`: reset CYT learning/session state before each scored task;
- `persistent_session`: preserve session context suppression/reinjection state but do not treat it
  as TierManager learning;
- `sequential_adaptive`: preserve successful-tool-call TierManager history over one frozen ordered
  sequence and report predefined checkpoints.

A scored query must not silently mutate state used by later independent cold-start rows.

## Required per-run provenance

Record exact commits/versions for SchemaRouter, CYT, agent, model, MCP servers, and catalog; model
parameters; task/case digest; hardware/runtime; retry/timeout policy; state-regime identifier; and
all runner configuration. Raw traces must retain tool exposure, tool calls, usage, latency, and task
scorer output.

## Comparable outcomes

Primary end-to-end outcomes are task success, required-tool execution, total model tokens,
cumulative tool-schema/context bytes, agent steps, tool-call counts, end-to-end latency, and cost
when reproducibly exposed. Routing-only metrics remain secondary diagnostics.

Do not claim independent validation from this contract or from maintainer agreement alone.

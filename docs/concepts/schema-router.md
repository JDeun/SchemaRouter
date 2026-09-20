# What SchemaRouter is

SchemaRouter is a **schema-aware planning and execution layer**.

Its job is narrower than a general agent framework and deeper than a semantic tool router.

## The compilation model

A conventional router often produces one decision:

```text
Query -> Tool
```

SchemaRouter produces a typed execution plan:

```text
Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Evidence requirements
  -> Schema fingerprint
  -> Execution policy
```

That plan is validated again immediately before execution.

## Why endpoint identity matters

One API or MCP server can expose many operations. Treating the server as a single "tool" loses the
difference between:

- a read operation and a mutation;
- a search endpoint and a detail endpoint;
- different required parameters;
- different output schemas.

SchemaRouter therefore makes `EndpointSpec` first-class instead of assuming one endpoint per tool.

## Why response fields matter

Fetching every field can waste context, expose irrelevant data, and increase downstream model cost.
Pruning too aggressively can also destroy recall.

SchemaRouter uses **recall-preserving projection**:

- keep confidently relevant fields;
- retain identifiers;
- when intent is ambiguous, prefer the declared field set instead of risky over-pruning.

## Why the executor validates again

Plans are not execution authority. Between planning and execution:

- schemas may change;
- a manually constructed `ToolCall` may be malformed;
- a model may have proposed an invalid value;
- a bound transport may no longer match the registered contract.

The executor therefore recomputes required arguments, checks fingerprints, applies policy, validates
input, invokes the trusted transport, validates raw output, and only then projects fields.

## Non-goals

SchemaRouter does not try to own:

- chat message abstractions;
- prompt-template ecosystems;
- model-provider clients;
- conversation memory;
- graph orchestration;
- checkpointing.

Those concerns belong in surrounding frameworks such as LangChain or LangGraph.

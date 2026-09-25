# What SchemaRouter is

SchemaRouter is a **schema-aware planning and execution layer**.

Its job is narrower than a general agent framework and deeper than a semantic tool router.

The ownership boundary is explicit:

| Layer | Owns |
| --- | --- |
| Application / agent framework | conversation, agent loop, graph, model strategy, memory, checkpoints |
| SchemaRouter | typed tool/endpoint planning, schema identity, validation, policy, execution boundary |
| Optional decision backend | one bounded selection over finite locally authorized candidates |
| Capability source | OpenAPI, MCP, OPTIMADE, Python callable, approved adapter/plugin |

A decision backend such as Laya, Ollama, or Jev is therefore not a nested agent. It cannot decide
to start another tool loop, invent a capability, or grant execution authority.

## The compilation model

A conventional router often produces one decision:

```text
Query -> Tool
```

SchemaRouter produces a typed execution plan:

```text
Query
  -> semantic data need
  -> required response fields
  -> provider / access path
  -> tool / endpoint
  -> parameters
  -> evidence requirements
  -> schema + tool fingerprints
  -> execution policy / availability
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

Fetching every field can waste provider bandwidth, increase latency, pollute downstream model
context with irrelevant values, and consume unnecessary prompt tokens. SchemaRouter therefore uses
**field-first, route-second** planning: determine the logical fields first, then choose a route that
can provide them.

When a query-to-field match is clear:

- keep only confidently relevant fields plus identifiers;
- push those fields upstream when the endpoint has an explicit `ServerProjectionSpec`;
- validate the raw projected response;
- perform final local projection before producing the `ToolResult`.

Pruning too aggressively can also destroy recall. When field intent is genuinely ambiguous, the
default planner prefers the declared field set rather than pretending one field is sufficient.

See [Field-first execution](field-first-execution.md).

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

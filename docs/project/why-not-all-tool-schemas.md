# Why not send every tool schema to the model?

SchemaRouter 0.17.0 is a typed capability routing and governed execution layer for AI agents. It
exists for systems where an agent can reach many APIs, MCP servers, SDK functions, or data stores,
but the surrounding application still needs a bounded and auditable execution boundary.

The tempting alternative is simple: serialize every available tool schema into the model context
and let the model choose. That can work for small catalogs. It becomes less attractive when the
catalog grows, schemas overlap, authorization differs by caller, or a selected operation can mutate
remote state.

## Retrieval is only the first boundary

SchemaRouter does not treat a retrieval score as execution authority. It compiles heterogeneous
registrations into typed capabilities, retrieves a bounded candidate set, and validates the chosen
route again before execution.

A capability can carry more than a tool name:

- endpoint identity and schema fingerprint;
- typed parameters and output fields;
- units and field semantics where known;
- current execution binding and availability;
- principal/policy constraints;
- mutation and destructive-operation classification.

This makes the shortlist useful to an agent without making the shortlist itself trusted.

## Field-aware context instead of whole-catalog context

Large tool catalogs create two separate problems: selecting the right operation and deciding how
much schema context to expose. SchemaRouter can retrieve a small set of relevant capabilities and
project the output contract to the fields needed by the task.

In the controlled 0.14 B1 mechanism experiment, the SR-5 condition preserved 100% required-route
recall on that frozen surface while exposing 5.42% of FULL tool-schema tokens. Task pass was 91.30%
for SR-5 versus 68.48% for FULL, with zero unauthorized destructive executions. These numbers are
mechanism/sanity evidence from a controlled benchmark, not a claim that every agent or catalog will
see the same improvement.

The stronger-agent B2 replication and the remaining held-out/final-answer experiments are tracked
separately. SchemaRouter deliberately keeps development diagnostics and external-validation work
out of stable product claims.

## Unsupported requests need a policy boundary

A router should not be forced to choose a tool when no registered capability supports the request.
SchemaRouter therefore separates candidate retrieval from execution policy and can fail closed at
the runtime boundary.

That distinction matters most for mutation. A model selecting a destructive-looking route does not
grant permission to execute it. The host supplies verified principal context and policy; the runtime
revalidates arguments, schema identity, authorization, availability, and output contracts.

## Provider and transport are not the product boundary

Applications often care about a provider before they care whether its interface arrived through
OpenAPI, MCP, a Python SDK, GraphQL, a database adapter, or another protocol. SchemaRouter therefore
normalizes those ingress paths into a common capability model.

It does not own credentials, connection pools, authentication, conversation memory, decomposition,
or final answer generation. Those remain responsibilities of the host application or agent
framework. SchemaRouter is intended to compose with them rather than replace them.

## Schema and health are lifecycle state

A route that existed at registration time may not remain executable forever. Providers change
schemas, transports fail, and local bindings disappear. SchemaRouter keeps schema identity and
execution availability explicit so a stale candidate does not silently become trusted execution.

This is also why retrieval and execution are separate APIs: discovery can remain side-effect free,
while executable retrieval and runtime validation can account for current bindings and policy.

## Framework composition

SchemaRouter is not another general agent loop. LangChain, LangGraph, LlamaIndex, custom planners,
and other orchestrators can remain responsible for reasoning and workflow state. SchemaRouter sits
below that layer as the typed catalog and governed execution boundary.

That narrower scope is intentional. A project can adopt the routing/execution contract without
moving its prompts, memory, checkpoints, or application state into SchemaRouter.

## What 0.17.0 does not prove

The project is Beta / pre-1.0. Public APIs can still evolve.

The current research evidence does not establish population-level superiority over every full-schema
agent setup, and development comparisons with external systems such as SmartMCP, Clear Your Tools,
Jev, and HYSET are not treated as independent held-out validation. Those tracks remain explicitly
separate until their frozen protocols produce reproducible results.

Likewise, SchemaRouter is not an identity provider, database proxy, arbitrary query executor, or LLM
gateway. Database-native grants, RLS, ACLs, network controls, and caller-owned credentials remain
authoritative.

## A practical adoption path

Start with one real provider or tool family, register it through the most natural ingestion path,
and inspect the compiled capabilities before adding more catalog breadth. Keep execution policy
deny-by-default for remote mutation. Measure required-tool recall, exposed schema context, final task
success, and failures separately rather than optimizing only a retrieval score.

The stable 0.17.0 release, quickstart, examples, security model, and current research status are all
kept in this repository so product guarantees and experimental evidence can be audited separately.

- [SchemaRouter README](../../README.md)
- [Quickstart](../getting-started/quickstart.md)
- [Execution boundary](../concepts/execution.md)
- [Security model](../security/threat-model.md)
- [Research status](../research/routing-status.md)
- [Adoption scorecard](adoption-scorecard.md)

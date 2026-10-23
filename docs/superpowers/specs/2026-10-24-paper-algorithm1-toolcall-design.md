# Original-paper Algorithm 1 — source-attested ToolCall projection (P2 slice)

**Decision:** Implement the host-only, opt-in ToolCall *projection* of the already proved P1 `PaperFieldCoverage`, preserving exact original route identities, fields, and producer→consumer input dependencies. This is the first #1560 implementation slice, not full Algorithm 1 or executable multi-hop orchestration.

## Goal and limits

The original paper concludes discovery with a tool, endpoint, argument, response-field and evidence plan. P1 presently stops at immutable complete-field route receipts. The next user-visible operation must bridge those receipts to the existing `ToolCall` model so a host can inspect the actual required call sequence without teaching the router to invent data-dependent arguments or run an agent.

Every call still passes the existing authorization and executor gates if the host later explicitly invokes it. Discovery/projection never invokes registered tools, never sets permissions, never modifies normal `plan`, `retrieve` or `execute`, and never creates a graph/index. It must not pretend that a producer result or an unbound downstream argument is already available.

## Considered implementations

1. **Selected: explicit opt-in nonexecuting ToolCall recipe** over fresh, same-snapshot P1 field coverage. For direct calls, use exactly the already selected source-visible field names. For one-hop and same-root forks, retain ordered original producer/consumer `ToolCall`s with unresolved dependency parameters and a structured binding receipt. A P1-qualified, explicitly host-approved typed inputful G5 root may appear with its declared required host inputs marked **missing**; no value is bound. Reuse `SchemaPlanner._evidence` and the existing `ToolCall` class; never call the planner's top-K selector again and accidentally choose a different route. Benefit: first integrated paper output with no change to source selection. Limit: no concrete host root argument binding or actual execution yet.
2. **Deferred: route every selected step back through `SchemaPlanner.plan`.** Existing ranking cannot pin a specific authorized endpoint from a P1 receipt and might return a different route; thus it is not a safe compilation method without new pinning logic.
3. **Rejected: generate a new execution graph/agent pipeline.** It duplicates G5 and risks elevating structural input bindings into live argument values.

## Interface and safety contract

`compile_paper_field_toolcalls(router, query, *, principal, catalog, index, k=5) -> PaperFieldToolCallPlan` returns the same P1 disposition, snapshot, registry version and bounded alternatives. A complete alternative contains tuples of existing `ToolCall` objects in source→consumer order and `PaperFieldArgumentDependency` receipts indexed by step. A dependent `ToolCall` has `missing_required_arguments` for the exact source-bound inputs; its `arguments` is empty and its `executable` property remains false. A source-input-free call has no fabricated argument. An inputful root needs the original G5 index's explicit host approval and exact `_host_source_input_names` contract: its `post_id`-like argument is also **missing**, and the root remains nonexecutable. The containing plan always has `executable_authority=False` and is never executed inside the API.

The compiler rereads the native original ToolSpec and current scoped EndpointSpec, checks policy, fingerprints, availability, read-only and field visibility, validates that *every* binding references a preceding call, a declared consumer parameter, an original producer output, and no duplicate target, then performs a fresh P1 proof comparison before returning. Any mismatch fails closed; a second observation cannot provide cross-provider atomicity after return.

This slice supports P1-qualified no-input routes, G5-reviewed inputful root *descriptors*, one-hop and same-root two-consumer forks; it abstains for unsupported OPTIMADE search parameters. Host-bound complete **concrete** input values and later execution through the existing executor require a separate qualified extension. The outer dataclasses are frozen, but nested Pydantic `ToolCall` values remain mutable; this is a descriptive recipe, not a tamper-proof persisted attestation. Quality, source-independent E2, production default and v0.18 release HOLD remain unchanged.

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

## P2.1: optional indexed direct FieldGroup qualification (2026-10-24)

**Intent:** #1560 requires catalog-wide source-attested retrieval without rescanning every endpoint for each query. The existing `NativeSchemaPostingIndex.lookup` and `retrieve_authorized_concept_graph(experimental_indexed_direct=True)` already implement an index-backed conjunctive *direct* route. P1/P2 must be able to opt in to this original source-backed implementation and measure it under the same declared query, principal and K5.

**Considered approaches:**

1. **Selected:** add keyword-only `experimental_indexed_direct: bool = False` to P1 retrieval, P2 compilation and both P2 receipt binders. Pass it to the existing concept-graph direct selector and preserve the choice for each nested re-proof. No new index, ranker, graph edge, parsing semantics or provider call.
2. **Rejected:** post-filter conventional top-K or copy the posting lookup into the paper compiler. This changes pre-K completeness and duplicates an authorization surface.
3. **Deferred:** switch default/direct ranking to the index globally. The indexed direct path has no measured ranking quality or independent E2, and must not silently replace product defaults.

**Acceptance:** complete direct field-group and typed fork receipts must have equal status, required semantic coverage, original source IDs and visible field sets in both modes; relative ordering is **not** a ranking-parity promise. No hit, source denial, data-scope hiding, over-K and source drift must fail closed. Invalid option types fail before source lookup; binders must re-prove with the exact chosen mode. Run deterministic 500/5000-source E0 comparisons and CPU timing if feasible, reporting cold index build separately from warm query and never inferring answer quality/cost from schema-only timings.

**Receipt compatibility:** the compiler must store the chosen mode in an optional trailing P2 dataclass field so a replay under a different mode is rejected. Legacy constructor arguments and the default retrieval result remain valid, but a serializer of this *opt-in* P2 dataclass will see the new `experimental_indexed_direct=False` field; no byte-for-byte serialization compatibility is promised.

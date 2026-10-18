# G2 research: authorized source-pinned two-hop field-aware graph paths

Date 2026-10-18. Issue [#1540](https://github.com/JDeun/SchemaRouter/issues/1540).
Based on the [original SchemaRouter paper](https://arxiv.org/abs/2608.21375),
paper↔code alignment [#1530](https://github.com/JDeun/SchemaRouter/issues/1530),
single endpoint conjunctive FieldGroup E1 #1536, and the native verified G1
producer→consumer predecessor research #1539.

## The original agent-neutral boundary

SchemaRouter manages a *registered internal ontology/typed schema graph*.
It searches and **proposes** a small set of authorized, source-verified tool
dependencies. The **external agent** decides whether/how to use the tools,
chooses the order, values and final answer. **The host** independently checks
authority for any explicitly invoked action. An inferred multistep executor
or agent loop is not part of SchemaRouter.

## Concrete, opt-in G2 research experiment

`scripts/research_verified_graph_paths_g2.py` extends G1's
`_safe_routes` principal-scoped native catalog to a bounded 1–2 edge
graph-path proof. A **trusted host** declares one input `semantic_id` per
real, required native `ParameterSpec`, pinning each declared route's
original registered `EndpointSpec.fingerprint`. This external declaration
is required because native `ParameterSpec` itself **does not** store
semantic IDs. No parameter-name semantic inference occurs.

Only read-only, non-destructive, currently authorized and available
endpoints with explicit source-type and license metadata are eligible.
A parameter-free root must emit a trusted **identifier** `FieldSpec`
that matches the downstream required input semantic, exact unit and
typed scalar schema; each consumer must have exactly one fully bound
required input in the strict G2 condition. Arbitrary input schema,
credential/header/body-root inputs, unexpected additional inputs,
unqualified units, missing field metadata, non-identifier joins,
unsupported `pattern/enum` JSON constraints and implicit conversions
are NOT accepted as proven bindings.

The full target must provide **every** host-declared required output
semantic field, type and unit, not just one relevant match. Source
revision receipts are assembled from principal-scoped endpoint
fingerprints into a validated native `CapabilityGraphSnapshot`, with
the declaration digest in `builder_version`. Traverse the native
`snapshot.build_graph().predecessors` relationships backward from the
target, return only complete source→target paths that originate at a
verified parameter-free root, and reject cycles. The result contains
**route and field binding references only**, no values, provider data,
promised data availability, LLM prompt, execution plan or permission.

Strict bounds: `K=5` complete paths, max 2 hops, <=512 authorized routes
and <=4096 output fields via G1, <=2048 validated graph edges, <=128 walk
states, <=32 declared bindings and small fixed alias/field groups. Reject
over-budget rather than silently truncate or refill after seeing gold.
The current registry-version, authorization-policy and availability
predicate witness must remain unchanged through output.

## Evidence and limitations

Linux no-network E0 tests include exact declared EN/KO/JA queries, a
source→structure→property positive (two valid identifier joins),
missing/mis-typed producer/consumer, missing target FieldGroup member,
wrong output unit, hidden producer identifier/output, denied target,
stale source schema, over-K paths and no executor/agent calls. This is
**synthetic authored coverage**, not an independent multilingual
performance or task-completion result.

Crucially, G2 does **not** claim to handle arbitrary multi-hop plans,
multiple independently required inputs, mixed-source join policies,
provider runtime values, nested/ref JSON Schema equivalence, unit
conversion, source licensing *legal clearance*, automatic semantic
link learning, new `retrieve_authorized` defaults, or commercial quality.
It refuses unsupported input contracts, including source credentials,
rather than guessing correctness.

The next qualification must compare true required-route/field-set
recall with the unchanged native lexical K5 and G1 on independent
publisher-authored #1346 EN/KO/JA tasks, unsupported rejection,
actual tokenizer counts, warm Linux CPU p50/p95/p99, freshness/drift,
and #1477 external-agent task outcome. Preserve the #432 frozen
negative benchmark and v0.18 #1356 HARD HOLD.

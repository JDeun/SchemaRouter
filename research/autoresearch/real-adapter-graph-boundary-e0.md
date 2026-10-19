# Protocol-neutral native graph: real adapter boundary E0

Tracks [#1545](https://github.com/JDeun/SchemaRouter/issues/1545), the
original graph-first mission [#1530](https://github.com/JDeun/SchemaRouter/issues/1530)
and the nonexecuting G2 work [#1544](https://github.com/JDeun/SchemaRouter/pull/1544).

## Exact scope of this experiment

This is an **offline parser-contract qualification**, not a remote API run or
general interoperability benchmark. Unlike synthetic `adapter_origin` labels,
the test calls production `tool_from_openapi`, `tool_from_mcp`, and the
OPTIMADE production discovery converter `_tool_from_discovery` on locally
authored source-document fixtures, then registers all three resulting actual
`ToolSpec` contracts in one `SchemaRouter`.

- A real OpenAPI parameter-free GET publishes the explicit input envelope\n  `{type: object, properties: {}, additionalProperties: false}`. G2 now\n  proves this *exact* safe empty contract can serve as a root without\n  deleting the schema; extra JSON Schema constraints prevent the edge.\n- OpenAPI contact-ID producer and MCP case-status consumer can form a single
  proven typed graph edge **only after locally trusted authorization, immutable
  native source fingerprints, source/license labels, exact output and input
  semantic IDs, and a trusted read-only classification are explicitly supplied**.
  Tests include English, Korean and Japanese declared query aliases; these
  aliases are authored fixtures, not a measured multilingual generalization.
- A remote MCP `readOnlyHint` annotation cannot by itself make a tool eligible.
  The original `inputSchema` is retained; unknown `additionalProperties`
  constraints cause strict G2 abstention instead of silent schema removal.
- The real OPTIMADE `get_structures` input `minLength: 1` is retained. The
  current strict graph helper cannot prove support and abstains. This is an
  intentional unsupported-contract result, **not a failed provider call**.
- Hide the contact identifier by the principal's data scope and the graph must
  return no path. The same catalog remains usable for a permitted principal.
- Output contains graph hints only: no argument values, invocation, planner
  or agent loop. No production `retrieve_authorized` ranking or K5 default
  is changed.

## Remaining qualification before any product promotion

1. Extend audited locally trusted semantic amendments to arbitrary discovered
   sources without allowing remote text to grant execution rights.
2. Qualify supported real JSON Schema constraints (`minLength`, enum,
   oneOf, auth envelopes) conservatively without discarding the provider
   schema. Record explicit rejection categories.
3. Independently sourced live OpenAPI/MCP/OPTIMADE provider transfers and
   domain-disjoint EN/KO/JA route/field recall, false-acceptance, and CPU
   latency p50/p95/p99; then paired external agent E2 on #1477.
4. Preserve native schema graph snapshots, auth/data-scopes, default Top-K,
   frozen #432 negatives, external #1346 and v0.18 release #1356 HOLD.

This fixture does not establish a new cross-origin semantic equivalence,
protocol-wide support, provider authority, dataset license or end-task result.

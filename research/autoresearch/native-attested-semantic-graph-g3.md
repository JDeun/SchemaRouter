# G3 E0: host-attested native input ontology to G2 typed paths

Issue [#1547](https://github.com/JDeun/SchemaRouter/issues/1547).
Mission [#1530](https://github.com/JDeun/SchemaRouter/issues/1530);
merged native model [#1543](https://github.com/JDeun/SchemaRouter/pull/1543);
canonical graph [#1544](https://github.com/JDeun/SchemaRouter/pull/1544);
mixed adapter source-contract qualification [#1546](https://github.com/JDeun/SchemaRouter/pull/1546).

## Research-only design

The caller provides a small, **locally host-approved** allowlist of original
registered native tool+endpoint fingerprints with an explicit target and
required output `CapabilityFieldContract` group. G3 does not invent an
approval from remote MCP annotations, arbitrary OpenAPI descriptions, input
parameter names or agent text.

For a supported nonroot route with one required input, G3 reads the
**registered native `ParameterSpec.semantic_id`**. It does not also ask the
host to duplicate that semantic in a separate G2 input mapping. Every
approved source revision is checked against both the entire registered
`ToolSpec.fingerprint` and selected `EndpointSpec.fingerprint` before
mapping. Roots require no native input parameter; consumers in this E0
require precisely one fully declared required scalar argument.

The scoped G1 helper accepts an opt-in exact approved-route subset, so
its existing 512-route/4096-field **research graph accounting** applies
to approved graph nodes before source and K scanning. This is tested
against 520 additional unreviewed registered routes; it does not imply
full-catalog indexing or production latency improvement.

The existing `retrieve_verified_graph_paths_g2` performs the full
principal-/field-scoped, currently available, provenance-aware capability
snapshot build and fixed K5 typed one/two-edge graph traversal. The additive
`allowed_route_ids` filter scopes all graph nodes **before** edge discovery
and K counting; without this opt-in argument, G2's original behavior is
unchanged. Output remains route IDs, producer fields, consumer parameter
references, complete target FieldGroup and scoped snapshot digest. No source
is invoked and no argument values or execution plan are inferred.

## E0 controls

- A second offline integration test uses **real production** `tool_from_openapi`
  and `tool_from_mcp` schema converters; local source-owner revision
  explicitly annotates the identifier field and native MCP input semantic,
  then host-attested G3 proves the OpenAPI→MCP one-hop path in EN/KO/JA.
  This is not real network discovery or proof of live provider success.
- Exact authored EN/KO/JA aliases, scholar-reference non-material chain
  `papers.read → citations.read → claims.read`, complete two-field goal and
  result parity with explicitly declared pinned G2.
- A matching but unapproved fourth source is excluded *before* graph build.
- Hidden producer ID, denied policy, absent native semantic, incompatible
  input type, extra unproved input JSON Schema, stale full-tool/endpoint
  fingerprints, duplicate approval, K drift, undeclared query, or agent
  execution attempt do not yield a valid path.
- The declared host approval is a **trust boundary**, not legal clearance,
  provider evidence, or an execution authorization. Do not infer semantics
  or attest sources automatically from remote discovery.

## Open evidence gates and limitations

- This E0 is *synthetic, no-network* graph parity, not independent query
  understanding, real API multi-hop payload transport or agent task success.
- E0 G2 conservatively supports zero-input roots and one fully declared
  scalar input for each subsequent step, <=2 edges and fixed K5. Complex
  `oneOf`, `enum`, units/conversions, body/auth schema and multiple
  required inputs remain unsupported unless independently proven.
- Native annotations are a metadata source; the trusted local fingerprint
  approval does not prove correctness of the authored ontology itself.
- Integrate production graph search only after independently authored
  #1346/#1339 route+field recall and field-scope negatives, CPU p50/p95/p99,
  and actual paired agent E2 #1477. Do not alter default
  `retrieve_authorized`, frozen #432, or held release #1356.

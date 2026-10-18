# G5 E0 — indexed native schema graph candidate discovery

Source [#1560](https://github.com/JDeun/SchemaRouter/issues/1560),
increment [#1562](https://github.com/JDeun/SchemaRouter/issues/1562),
native source index [#1561](https://github.com/JDeun/SchemaRouter/pull/1561),
bounded G4 [#1559](https://github.com/JDeun/SchemaRouter/pull/1559).

**North star:** SchemaRouter indexes heterogeneous registered native schemas and
returns scoped top-K tool/field candidates to a separate agent, not an agent
planner or executor.

## Source, index and canonical graph

`NativeSchemaGraphIndex.build(field_index)` traverses the ONE original
registry once at build time, pinning its exact `ToolSpec` and
`EndpointSpec` fingerprints via `NativeSchemaPostingIndex`. Only a
parameter-free, read-only, provenance-stated source producing a native,
typed, unitless `identifier=True` field can form a root. A consumer must
have exactly one source-attested required scalar `ParameterSpec.semantic_id`
with a provable exact input object schema. Other required parameters,
JSON Schema constraints, unavailable/unknown input maps and missing source
metadata do not create a graph edge.

For source→consumer type compatibility, **use existing**
`build_capability_dependency_graph`, which already has the semantic-ID
producer index and canonical `compare_capability_composition`.
This is not another graph DB, planner or ranker.

At query time: declared EN/KO/JA concept → complete typed FieldGroup →
full-catalog scalar output postings intersection → source-indexed
consumer route → canonical typed graph `predecessors(target_id)` →
original principal-scoped, currently available and read-only native
producer/consumer pair → verified native field names and pinned revisions.
No known target-route ID, task gold, values, invoker, plan or tool call is
passed to G5. Current policy/field scope is evaluated **before** exposing
any candidate; users do not receive the raw authority-neutral graph.
Strict fixed K5 and explicit `over_k_unranked` with no candidates
rather than quality-unproven lexical truncation.

## Limits / blockers

- Native one-hop root→single-input consumer only. No arbitrary multi-hop
  sources, field joins, transforms, conversions or inferred equivalence.
- `identifier=True`, `source_type`, `license`, semantics and read-only
  declarations are **host-trusted**; source assertions aren't proof of
  legal access or provider execution authorization.
- Build scans every registered tool; query uses posting intersection and
  graph predecessor adjacency, not a new full-registry scan. This is a
  correctness/complexity property, not a measured latency/RSS/throughput
  SLO or statistical retrieval advantage.
- Offline tests of real production OpenAPI and MCP parsing use
  developer-authored local contracts, not provider-live calls. A >=5100
  registered route test is synthetic. No independent EN/KO/JA E2 cohort
  or model/host task success exists.
- Graph capability contracts are structural hints; the separate agent
  must verify authorization, credentials, values, policy and provider
  state anew immediately before any execution.
- No modifications to default `retrieve_authorized`, frozen #432,
  or v0.18 release HOLD #1356.

Next: protect version/availability/policy witnesses under adversarial
concurrency, independently measure 5k p50/p95/p99/RSS and recall against
an exhaustive scope-safe oracle, provide quality-ranked Top-K5 when >5,
then #1346 publisher-owned gold and #1477 real paired E2.

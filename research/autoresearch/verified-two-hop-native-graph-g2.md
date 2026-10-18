# G2: native two-hop typed graph hints on one authorized snapshot (E0)

Architectural gate [#1530](https://github.com/JDeun/SchemaRouter/issues/1530),
multi-hop issue [#1540](https://github.com/JDeun/SchemaRouter/issues/1540),
one-hop dependency [#1538](https://github.com/JDeun/SchemaRouter/issues/1538)
and the [original field-aware SchemaRouter paper](https://arxiv.org/abs/2608.21375).

This is an **opt-in scripts-only** proof of graph relation composition.
It is **not** an agent, executable plan, production ranking improvement or
independently supported task success.

## What G2 actually verifies

The trusted host declares two `DeclaredQueryInputLink` contracts:

1. A fixed intermediate native endpoint with exactly one required typed
   parameter bound to a declared semantic field that some authorized
   upstream route must produce.
2. A fixed final native endpoint with exactly one required typed parameter
   bound to the intermediate's declared output semantic field.
3. Both declared consumer endpoints are **pinned to exact native
   endpoint schema fingerprints**; the declared chain fails closed when
   an endpoint's schema changes or an alias/semantic relation is wrong.
   EN/KO/JA query aliases are exact host-declared examples, **not**
   automatic natural-language translation.

**All graph vertices** come from one current native registry projected by
the current principal's authorization, field scope and availability. Only
read-only/non-destructive routes, scalar typed fields with verified simple
JSON shapes, and source type/license/provider declared by the source
are eligible. Use one `CapabilityGraphSnapshot` with visible source
endpoint fingerprint receipts and native
`snapshot.build_graph().predecessors(...)` edges to establish a strict
`upstream → declared intermediate → declared final` path.
Require the final visible endpoint to provide every host-declared
answer-field semantic in the final group.

An upstream source whose **own required parameters are not established**
is not returned: in G2 research we conservatively require the upstream
producer to have *no* required native inputs. This does not prove that its
optional arguments can be filled or that any actual response will
contain the required identifier. Graph adjacency and eventual runtime
argument materialization are distinct responsibilities.

G2 returns only immutable
`NonExecutableTwoHopHint` objects containing two native
`NonExecutableDependencyHint` edges, required final semantics and
the authorized graph snapshot digest. It never calls, plans, executes
or constructs tool arguments. The external agent remains responsible
for the task and any requested execution must pass the host's existing
security boundary.

## Deliberate fail-closed scope

- strict K5 and **exactly two graph edges**, at most 512 authorized
  read-only routes, 4096 visible output fields, 1024 graph edges; reject
  >K eligible source paths rather than silently truncating as if ranked
- missing/unknown typed input/output, extra required argument,
  unsupported JSON Schema patterns/enums, implicit conversion, missing
  provider/license/source metadata, denied route, hidden field,
  mutating route, missing final field and stale consumer fingerprint
  cannot qualify
- graph only verifies native typed requirements; it cannot validate
  provider runtime values, remote source licensing terms, complex
  conditional JSON Schema, cycles deeper than two edges, source
  availability over time, chained material identifier values or
  side effects. Source/license labels are metadata gates, **not**
  commercial-use approval
- no independent source/gold, language generalization, K5 ranking
  quality, CPU p95 production target or final task completion claim.
  Existing frozen #432, independent intake #1346 and release
  #1356 **HARD HOLD** remain unchanged

## Further work required for product parity

The original paper's full graph retrieval needs versioned semantic
input bindings within the trusted tool registration itself (native
`ParameterSpec` still has no semantic ID), nontrivial FieldGroup and
identifier joins, bounded graph search over candidate tool choices,
source license/provenance validation and independent EN/KO/JA
route/required-field + E2 agent metrics (cf. #1339, #1477, #1346).
No E0 script may be promoted as the default based on synthetic tests.

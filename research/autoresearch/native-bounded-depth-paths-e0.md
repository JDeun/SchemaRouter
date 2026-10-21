# #1560 — Bounded depth 2–4-hop typed source graph retrieval (E0)

The user correctly flagged that 2-hop cannot cover every tool dependency chain.
A real workflow might require 3, 4 or more intermediate data transformations,
and **fan-in/fan-out DAG joins** are not equivalent to a longer linear chain.

## Opt-in API

`NativeSchemaGraphIndex.lookup_bounded_paths(..., hops=3, k=5)`
proves **exactly** the declared number of typed, source-owned graph edges,
currently restricted to 2–4. This is a deliberate E0 safety envelope rather
than an assertion that four hops can handle every use case.

The method reuses the single existing `CapabilityDependencyGraph` and
`NativeSchemaPostingIndex` and their canonical typed comparator. It:

- anchors a **host-approved** query alias and conjunctive output FieldGroup
  at a single terminal original endpoint;
- traverses only the canonical typed graph's predecessor lists, not all
  registered native tools on each query;
- checks original versioned tool/endpoint fingerprints, current principal,
  authorization policy, health and scoped fields for every route;
- checks every edge's complete required scalar identifier parameters with
  the same `_root_field` and same-record proof as the older native G5 path;
- permits only a genuine zero-input or explicitly host-approved root;
  intermediates must each have complete typed required inputs;
- forbids repeat identities/cycles; caps graph expansions at 256 and
  qualified paths at 32; and keeps strict K=5 and unranked >K abstention;
- **rechecks every qualified original route and typed binding** after
  all health probes, including when the final result would be an
  overflow count, without returning private untrusted callback messages.

No model, translated alias guess, execution loop, dispatch token,
tool invocation, catalog scan, extra graph database or production change.

## Correctness scope / comparison

The E0 test suite defines source-owned chains with two, three and four
typed edges, including EN/KO/JA trusted aliases, exact original
fingerprints and binding positions, wrong intermediate type,
denied/hidden intermediate, incorrect depth, 6-path over-K abstention,
300 unrelated source route non-scan, same-object late availability
revocation, malformed depth, stale catalog, private callback exception,
and **exact 2-hop evidence parity with existing opt-in #1684 API**.

These are local research fixtures, NOT real publisher-authoritative tasks.

## What must NOT be claimed

- 4-hop is **not a universal ceiling**; deeper legitimate DAGs exist.
- Typed schema graph paths **do not prove observed values** needed to
  bind arguments at runtime, co-occurrence for different records, or
  upstream data freshness; host executor must authorize again.
- Branching fan-in / multiple producer field unions require an explicit
  source-owned merge/reconciliation contract; no path of one length
  automatically solves them.
- Hard expansion limits can conservatively abort a valid dense graph.
  This is a reported `PolicyViolationError`, never silently truncated
  "high-recall" output.
- Strict >K5 is still unranked, no qualified production recall, latency
  service-level objective, model-agent success or independent #1346 E2
  evaluation. Source/license/availability revocation across hosts remains
  a distinct trust model.

Future work must measure the actual publisher-authored required-path
depth histogram and compare depth 1/2/3/4 versus candidate count,
false accept/refusal, field completeness, auth violations, tail CPU,
schema bytes and downstream #1477 paired agent task utility.
Only then set an appropriate default/optional depth budget and
consider >4-hop with case-blind observed evidence. Keep #1535/#1560
OPEN and v0.18 #1356 HARD HOLD. Frozen #432/#424 negatives unchanged.

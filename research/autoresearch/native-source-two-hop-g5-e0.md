# #1560 — Bounded source-attested two-hop G5 graph lookup (E0)

## Motivation

The canonical `CapabilityDependencyGraph` already indexes exact typed
producer/consumer compatibility, but the native G5 catalog index previously
classified an endpoint as **either** a source identifier producer **or** a
required-input consumer. A read-only endpoint that requires a source-owned ID
and itself emits a distinct, source-declared ID lost its outgoing edges.
Without both edges, a genuine `root → intermediary → target` path could not
be recovered, even with an explicitly approved output FieldGroup.

## Opt-in, no new planner

- Preserve `requires` **and** `produces` in the existing
  `CapabilityContract` for a safe intermediary with 1–4 strictly required,
  scalar, typed original input parameters, source owner-reviewed semantic
  IDs and identifier-only scalar outputs.
- `NativeSchemaGraphIndex.lookup_two_hop` reuses *the same indexed graph,
  original immutable source fingerprints, semantic posting intersection,
  current authorization, data scope, and health receipts*. The route chain
  must be exactly three **distinct** registered ToolSpec/EndpointSpec
  identities, with two fully bound typed joins.
- An intermediary is NOT treated as a zero-input authorized root by the
  existing `lookup`. Only an original zero-input source or a separately
  host-approved typed parameterized source may start a chain.
- Validate every required consumer input by the canonical
  `_root_field` + `compare_capability_fields`, and use original
  `_flat_same_record_source_contract` for multi-parameter matches.
  Unknown optional input, mixed nested records, missing semantic ID,
  hidden output, unavailable resource or denied route cannot qualify.
- Bound strict output K=5; above K returns `over_k_unranked` with no
  candidate identities. Enumeration is capped at 32 scoped source paths
  and fails closed on overflow instead of presenting a truncated count.
- Before publishing any candidate or candidate count, **revalidate all
  three current-scoped routes for every qualified chain** and both join
  maps after the entire scan. Generic `PolicyViolationError` suppresses
  untrusted provider callback errors. Any external caller executing these
  native routes must independently authorize execution again.
- Only graph index predecessor lists are touched at lookup; there is no
  full ToolSpec registry scan, new graph database, agent loop, network
  transport, tool execution or new default retrieval behavior.

## Verification boundary

The new `tests/test_native_graph_two_hop.py` controls include EN/KO/JA
approved aliases, exact dual hop identifiers, original fingerprint witness,
wrong producer/consumer type, denied/hidden intermediary, stale registry,
untrusted alias, strict K, six-candidate abstention, unrelated 300-source
catalog non-scan, same-callable health withdrawal and private callback error.

**E0 local engineering only:** This neither proves arbitrary 2-hop workflow
execution/parameter *values* nor multi-provider interoperability, semantic
completeness or externally measured Recall@5. A two-hop **field-union** over
separate endpoints is not implied by these single-target required-field
checks; such a task needs distinct host-approved join/reconciliation
semantics. Strict source version does not imply distributed atomic health.
No fallback from no-fit to arbitrary endpoint, no learned ranker, no
publisher-independent E2, no production p95.

#1535 / #1560 stay OPEN; #1346 publisher-authored gold and #1477 agent E2
are prerequisites to default promotion. #1356 v0.18 HARD HOLD.
Frozen negative #432/#424 remain unmodified.

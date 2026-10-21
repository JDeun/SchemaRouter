# M1 #1560 — source-owned two-branch shared-root FieldGroup proof (E0)

## Why branching is not merely N-hop

A single 2/3/4-hop chain can satisfy a terminal endpoint's conjunctive
output fields, but cannot represent two independent consumers of the same
source identifier whose separate outputs cover distinct requested fields.

This narrowly-scoped research experiment is **NOT** generalized DAG
fan-in, result fusion, distributed query execution or natural-language
join inference. It is a bounded AND over **two independently authorized
original one-hop native G5 results**. Every source route and typed
binding is vouched for by the already-existing `NativeSchemaGraphIndex`,
`_root_field`, original tool/endpoint fingerprint, current health,
current policy and principal-specific field visibility.

## Strict assumptions

- Exactly two **distinct host-declared required semantic fields**,
  each satisfied at a distinct terminal read-only native endpoint.
- Both original native consumers have exactly **one** typed required input,
  bound to the **same field name of the SAME original, source-fingerprinted
  root endpoint**; consumer parameter *names* may differ.
- The shared source identifier must be a **required scalar property of a
  flat root output object**, with matching non-nested original field
  projections. Optional, array/nested, incompatible, hidden, ambiguous
  or unreviewed identifiers fail closed.
- The shared source root must have no input parameters. Arbitrary
  source-argument values or implicit auth cannot be manufactured.
- Root and both branches must remain authorized/visible/healthy.
  To catch a same-object callback invalidating an earlier arm, both
  one-hop result cohorts are re-probed and required to match byte-for-byte
  before any fork candidate/count is returned.
- Each one-hop arm uses existing **strict K5** and full source checks.
  If either cohort overflows, the entire fork result abstains without
  identities or a fabricated calibrated count. At most 25 pairs may be
  considered; >K5 proven forks are also count-only abstentions.
- All returned tuples are **schema evidence** only. The host must
  independently confirm a matching real-world row value and authorize
  executions before any result combination.

No default `retrieve_authorized` behavior, new agent/tool executor,
provider network operation, or second graph registry.

## E0 tests

`tests/test_native_graph_shared_root_forks.py` covers:

- Exact EN/KO/JA host-registered aliases and two distinct outputs;
- Single leaf cannot satisfy the complete two-field FieldGroup;
- Required flat same-source scalar key, scope/deny/unavailable/optional
  key negative controls;
- Six authorized one-field alternatives -> unranked strict K5 abstention;
- 300 unrelated registered native routes are never visited in lookup;
- Late live health withdrawal during two subgroup reads fails closed;
- Unsupported k/alias, stale registry and redacted host callback errors.

## Still open

A common typed source schema is **not proof of actual co-referent values**,
consistent snapshots across separate provider calls, permission to
execute, cross-provider legal authority, row-level join cardinality,
nested/array joins, three-or-more branches, independent source-native
publisher #1346 task gold, paired external-agent #1477 E2,
calibrated >K relevance, production p95, or end-to-end task success.
Conservative refusal is preferable to invented field-group recall.
`#1560` and `#1535` remain OPEN. v0.18 #1356 HARD HOLD.
Frozen #432/#424 negative cases remain unchanged.

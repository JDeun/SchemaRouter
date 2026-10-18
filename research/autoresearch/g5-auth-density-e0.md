# G5 E0 same-source candidate density and authorization matrix

Issue [#1566](https://github.com/JDeun/SchemaRouter/issues/1566),
parent synthetic CPU profile [#1565](https://github.com/JDeun/SchemaRouter/pull/1565),
original full-index milestone [#1560](https://github.com/JDeun/SchemaRouter/issues/1560).

## Why paired on the same graph?

A sole relevant path among >5,000 unrelated registered routes is
highly selective. It says nothing about the cost of field postings
with many structurally complete but unauthorized consumers. This
separate E0 profile builds **one** registry and **one** canonical G5
graph index for 5,131 synthetic registered routes: one identifier
producer, 6 output-field-complete type-compatible consumers, 24
source-complete but denied consumers and 5,100 unrelated routes.
All share the exact source revision, query `case status`, registered
typed fields, required parameter semantics and one-hop graph.

Only principal authorization differs: roles `zero`, `one`, `five`,
`six` have 0, 1, 5 and 6 allowed final consumers respectively.
All 24 denied typed consumers remain structurally valid but invisible,
and the six case must produce `over_k_unranked` with **no list**.
Expected route IDs are held only within the synthetic reference
assertions, not in user-facing aggregate reports.

Queries repeat after 5 warmups with the same catalog and concept
FieldGroup, 50 measured iterations by default for each principal.
Report includes per-role wall/process CPU p50/p95/p99,
aggregate candidate count, build cost, and whole process peak RSS.
It does not expose raw query strings, names of allowed/denied routes,
argument values, payloads or private provider metadata. Both
membership and output suppression are asserted before any timing.

## Evidence caveat

`E0_SYNTHETIC_CPU_NOT_INDEPENDENT` remains the ONLY tier: local
fixtures, fixed roles, expected matches and graph topology are
developer-authored. Not independent Recall@5, actual provider
calls, model use, real multilingual semantic inference, statistically
representative traffic or general performance superiority. The
process high-water RSS includes source construction and benchmark
code; timings on a shared runner cannot establish production SLO.

The next independent work is ranking over K, original
publisher-native #1346 query/route/field/permission gold, and real
agent E2 #1477. Preserve #432 historical negatives and v0.18 HOLD.

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


## First measured paired CI observation

Head `8a8a71bfec64559027dee58f821d89b25f1c4f3d`,
workflow `39173517181`, job `117811350597`,
GitHub Actions Linux `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39`,
Python 3.12.15. Fixed 5,131 synthetic routes, 24 unauthorized
typed distractors and 30 total compatible consumers. One shared
index, five warmups and 50 measured queries **for each role**.

| Principal role | Eligible / visible paths | G5 output | Wall p50 / p95 / p99 (ms) |
|---|---:|---|---|
| `zero` | 0 / 0 | `no_proven_hit` | 6.5357 / 7.8328 / 8.4579 |
| `one` | 1 / 1 | `complete` | 6.9069 / 8.1277 / 8.6360 |
| `five` | 5 / 5 | `complete` | 7.9701 / 8.1856 / 8.2912 |
| `six` | 6 / 0 | `over_k_unranked` | 8.2377 / 8.4050 / 8.6108 |

Index build wall 1,542.6894 ms; process peak RSS 108,296 KiB.
All 32 focused pytest tests + Ruff passed and Pyright reported 0
errors/0 warnings. These numbers are a **single synthetic CI run**.
Comparing the earlier 5,102-route/one-target 0.2292ms p50 against
this denser 5,131-route/30-syntactically-relevant-target 6–8ms p50
is **not** a controlled speedup or regression benchmark; the source
and authorization rule complexity differ. It is actionable evidence
that qualifying and filtering more posting-list candidates may be
materially more expensive in this particular design.


### Repeat on rebased main (same fixture, different CI run)

Rebased head `1bcdbaf7701e07d5989aabb4ac3f7a1cc8c049fd`,
workflow `39173716475`, job `117811951934`, same GitHub Actions
Linux kernel family/Python 3.12.15; 5 warmups plus 50 iterations per
role; 32 pytest cases and Ruff PASS, Pyright 0 errors.

| Role | Repeat wall p50 / p95 / p99 (ms) |
|---|---|
| `zero` | 5.2933 / 6.0336 / 8.0643 |
| `one` | 5.6007 / 5.8495 / 5.9469 |
| `five` | 6.4832 / 6.8099 / 7.3884 |
| `six` | 6.7937 / 7.6435 / 7.7315 |

Build wall 1,300.7612 ms; peak process RSS 108,284 KiB.
The different timing observations illustrate **CI runner noise**:
even this identical synthetic workload varies materially between
runs; neither single run establishes a stable SLO or independent
benchmark advantage. Both retain the same source/policy/return
correctness invariants.

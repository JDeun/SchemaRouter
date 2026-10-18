# G5 query selectivity, authority and broad posting E0

Tracked issue [#1567](https://github.com/JDeun/SchemaRouter/issues/1567);
parent CPU profile [#1565](https://github.com/JDeun/SchemaRouter/pull/1565);
registered indexed graph [#1563](https://github.com/JDeun/SchemaRouter/pull/1563).

## Why this experiment exists

The earlier single-query 5,102 synthetic ToolSpec benchmark measured
approximately 0.2292/0.2491/0.3387ms wall p50/p95/p99, but the query
matched exactly ONE typed consumer among mostly unrelated source schemas.
These numbers cannot be called whole-catalog speed/SLO or search ranking
quality. The next E0 profiles two separate stress factors:

- **Authorized completion density:** the SAME original registered native
  catalog includes one source identifier producer and seven matching
  typed consuming operations; use the source's principal-scoped host
  `AuthorizationPolicy`, native field visibility, and current availability
  to test one, five, seven (over-K), hidden-identifier, denied-producer
  and two temporarily unavailable consumers. The product never sees
  fixture-owned expected route IDs; those are used only in trusted DEV
  assertions after retrieval.
- **Semantic posting skew:** the SAME catalog has thousands of completely
  unrelated but valid `research.label` scalar output entries, so a
  broad declared research-label query triggers thousands of registered
  candidate reads even though no typed consumer with a required input
  exists. It must return `no_proven_hit`, but its latency is NOT presumed
  to equal the narrow CRM query's latency.

For each scenario, return only aggregate E0 status, authorized path count,
non-executable returned path count, wall and process CPU p50/p95/p99,
sample size and warmups; input source count, source index build wall and
whole-process peak RSS. No raw prompt, route list, arguments, task gold
or provider observations in JSON output.

## Data and model restrictions

All schemas, source revisions, truth paths, authorization roles and
ontology aliases here are **developer-authored**, not independently
publisher-certified. This benchmark never calls a provider API, invokes
an agent or executes a tool. Its fixed K5 semantics intentionally refuse
to emit an arbitrarily ordered five when seven complete paths exist.
Missing result is NOT calibrated out-of-domain inference, and typed
authorization means only local host-declared source policy.

`E0_SYNTHETIC_SELECTIVITY_NOT_INDEPENDENT` always appears in the output.
The broad semantic-posting case has few samples due to high cost, and
its p99 is a sample maximum rather than a statistically stable service
percentile. Host hardware, memory and cold-start differ from real traffic.

A source-independent 2026 publisher-native #1346 cohort and paired real
agent/provider E2 #1477 are still required to evaluate Recall@5,
field completeness, safety and completed task success.
Default `retrieve_authorized`, frozen #432 and v0.18 #1356 release HOLD
remain unchanged.

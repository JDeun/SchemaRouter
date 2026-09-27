# Operation routing quality roadmap

SchemaRouter treats routing quality as a constrained safety-and-performance problem, not as a single accuracy number.

The current 0.10 graph-projection research cycle retains its own preregistered promotion gates. Those gates must not be raised or lowered after observing development results. This roadmap defines the standing quality objective for later research cycles and eventual production-grade releases.

## Long-term target

| Metric | Long-term target |
| --- | ---: |
| Supported exact tool.endpoint accuracy | >= 85% |
| Near-domain unsupported-operation rejection | >= 97%, with 99% as the preferred high-safety target |
| False-route rate on no-route requests | <= 1% |
| Invalid-plan rate | 0% |
| Execution-authority violations | 0 |
| Mean latency | competitive with or below the paired production baseline |
| p95 latency | no regression versus the paired production baseline |

Safe abstention is preferable to an incorrect executable route. These values are project targets, not universal industry standards.

A production-quality claim also requires explicit structural authority evidence. Route membership
alone is insufficient: planned arguments and fields must remain declared by the selected endpoint,
schema/tool fingerprints must match the current registry, and fallback alternatives must satisfy
the same checks.

## Milestones

1. current preregistered research gate: >= 60%;
2. next research cycle: >= 70%;
3. strong beta: >= 75%;
4. serious OSS target: >= 80%;
5. production-credible target: >= 85%.

Unsupported-operation rejection and false-route safety should tighten rather than loosen while supported recall improves.

## Required reporting

A supported request counts as correct only when the expected tool.endpoint is selected exactly. A safe abstention on a supported request therefore reduces supported accuracy even though it is operationally safer than executing the wrong endpoint.

Report these dimensions separately:

- supported exact-route accuracy;
- near-domain unsupported-operation rejection;
- false-route rate;
- ordinary OOD rejection;
- invalid plans and execution errors;
- mean, p50, and p95 latency.

Do not collapse them into one headline number.

## Required slices

Every promotion-quality report should include per-language and per-route supported accuracy, worst-language and worst-route accuracy, false-route examples by unsupported-operation family, and paired gains/losses versus baseline.

## Research discipline

- Development data may select architectures and thresholds.
- A frozen candidate is evaluated on fresh calibration data.
- Blind data is generated or revealed only after candidate freeze and calibration success.
- Consumed calibration/blind sets never return to the tuning pool.

Historical results remain regression evidence, not tuning data.

## Architectural objective

request -> typed schema graph authority -> deterministic hard evidence -> semantic evidence attached only to authorized graph nodes -> bounded corroboration/negative evidence -> expensive reranking only for unresolved uncertainty -> safe abstention or typed execution plan

Semantic components may rank or veto registered routes. They never create tools, endpoints, fields, arguments, credentials, side effects, or execution authority.

## Production scorecard

Run scripts/evaluate_operation_routing_quality.py against a benchmark JSON report and planner name. The scorecard reads benchmarks/operation-routing-production-targets.json, evaluates the standing long-term gates, and reports language/route worst cases. It is deliberately separate from the promotion logic of an already-preregistered research cycle.

# G5 dense native fork same-index interleaved ABBA/BAAB E0, not E2

The previous source-native 500/5000-route +33/+64 dense fanout E0 A/B
tests (#1699 and #1702) ran two different fixture builds in a fixed order
and measured approximately 41–53% relative improvement on two runners.
Those results are not a controlled causal comparison and runner variability
was significant.

This opt-in follow-up constructs the *same graph object* and current host
principal once per cohort; after validating full EN/KO/JA source-native
result parity, it runs 10 alternating ABBA/BAAB rounds under both the fully
authorized dense 34/65 completed fork state and, later, the same graph
after the host availability predicate revokes the extra status routes.
There are 20 warmed wall/process CPU samples per scheduling mode per
condition; medians/p95/p99/means are metadata-only. The optional runtime
monkeypatch merely enables/disables **structural prepartition scheduling**
between queries. Every timed query executes original source/policy/health/
field/type rechecks and repeat completed-arm evidence in both modes.

The study is **developer-synthetic E0**, NOT representative distribution
or independent publisher-owned gold, model/agent route choice, actual HTTP,
production SLA or stable hardware causal proof. Although switching order
within one runner reduces time-order bias, it does not randomize workload,
model real concurrent requests or reproduce GPU/service latency; switching
health between conditions is itself a deliberate confound. Do not set
a performance target or claim release readiness from these numbers.

Preserve #1700/#1535/#1560 OPEN, independent source task/permissions #1346
and real agent E2 #1477 BLOCKED_EXTERNAL, v0.18 #1356 HARD HOLD, and
frozen historical #432/#424 negative controls unchanged.

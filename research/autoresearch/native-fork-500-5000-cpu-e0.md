# #1560 — 500/5000 route G5 shared-root fork, original-source reference (E0)

## Measurement goal

This extends the existing [G5 synthetic CPU/availability workflow](../../.github/workflows/indexed-native-g5-performance-e0.yml) to the recently merged opt-in *two-leaf shared-root* capability. It avoids creating another retrieval engine, registry, agent loop or provider executor.

A deterministic local developer-authored fixture registers exactly **500 and 5,000** source-native ToolSpec routes. Two read-only, single-output leaves consume one required flat scalar original CRM identifier and return `crm.fork_status` or `crm.fork_owner`. Noise routes, a separate already-existing CRM one-hop case route, principal policy, source type and license remain registered as genuine Source ToolSpec contracts.

The benchmark performs one **exhaustive original registry scan** in **benchmark code only**, without reading the indexed posting/graph adjacency, to derive the constrained reference route triple. This scans all source records with principal policy and scoped visible output fields. The reference uses shared field compatibility validation and only supports this predefined one-root/two-leaf topology; it is not a general authoritative oracle for all possible DAGs. Indexed lookup must exactly match the one reference fork; a silent missed/extra fork is a test failure.

## Required checks

- EN/KO/JA host-approved aliases: identical one-fork source-pinned candidate identities
- 500/5000 original registered routes: exact indexed vs exhaustive reference parity
- Source fingerprint and principal authorization already enforced by native G5; branch shared root and license checked in the existing implementation
- Same cached index with a dynamically unavailable owner consumer: no-fit and no disclosed candidate
- Strict K=5, `executable_authority=False`, `independent_quality_evidence=False`
- 5 warmup + 30 timed calls per catalog size on Linux Python 3.12
- Separate one-time graph/posting build wall ms and query process CPU/wall p50/p95/p99; process peak RSS includes fixture construction
- Machine-readable E0 JSON artifacts from GitHub Actions with explicit independent E2 flag false

The original E0 CPU benchmark for one-hop and the 5000 multi-endpoint source fingerprint A/B remains in the same workflow, untouched in computation.

## Non-claims

**No genuine publisher-authored tasks, no independent held-out query/route/field/permission gold and no real external-agent utility**. The aliases, fields, source contracts and expected topology were developed locally. This cannot confirm arbitrary deeper/fan-in joins or row identity, calibrated overflow ranking, production p95, service level, real API latency, data privacy outside the shown source policy, or actual tool execution. Benchmark-only exhaustive matching must **never become the product query path**.

Preserve #1535 and #1560 OPEN, #1346 source-independent benchmark intake and #1477 paired agent E2 as separate gates, #1356 v0.18 release HARD HOLD and frozen #432/#424 negative artifacts unchanged.

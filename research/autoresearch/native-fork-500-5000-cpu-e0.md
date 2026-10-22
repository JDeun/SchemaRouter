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

## Mixed-scope adversarial follow-up (2026-10-22)

The opt-in `--mixed-scope` arm preserves **exactly** 500 / 5,000 registered
routes while replacing six irrelevant noise routes with native confusables:

1. An otherwise matching status consumer explicitly denied to the principal
2. An otherwise matching owner consumer whose only output field is data-scope hidden
3. A matching owner consumer with an unreviewed license
4. A matching status consumer with a different declared source type
5. A matching owner consumer requiring an incompatible integer identifier
6. A matching root declaring the customer identifier optional instead of required

The separate original-registry scan is run on the *current principal-scoped*
source records, and the indexed fork must still return **only** the same
qualified root + two leaves. Tests directly check the denied route and
the wholly hidden consumer, EN/KO/JA result identity, and same-index policy
revocation. Existing 500/5000 sparse-run artifacts remain independently
reported; new `g5-source-fork-mixed-{500,5000}-e0.json` artifacts must never
be presented as real heterogeneous publisher or production SLA evidence.

These six negative controls do not establish arbitrary source/permission
adversarial coverage, publisher consent, row identity, Top-K ranking quality,
or external-agent E2 success; the exhaustive oracle remains topology-specific.

## Pre-join K5 false refusal (prospective E0 negative, #1560)

`tests/test_native_fork_prejoin_budget_negative_e0.py` freezes a **known
negative** for the current opt-in `lookup_shared_root_forks` design.
One genuine status+owner fork uses the registered `crm.fork_customer_id`
root. An unrelated second source-native root has a distinct typed semantic
identifier `crm.noise_customer_id` and six different status leaves sharing
the demanded *output* semantic ID. Each of those six is individually
authorized and source-typed, but **none joins the genuine owner leaf**.

The separately scanned original source reference has exactly **one**
legitimate shared-root two-leaf fork. In the current implementation the
status-arm one-hop lookup counts **seven** fully authorized paths and returns
`over_k_unranked` before common-root composition; the fork result then
abstains with zero disclosed candidates/qualified count. EN/KO/JA aliases
agree on the false refusal. With only the unrelated noise cohort disabled
by live availability (no index rebuild), the one genuine fork is returned.

This is a **VALID_NEGATIVE**, neither a privacy leak nor a retrieval success:
a real qualifying answer is refused because per-arm K5 is applied before
cross-field intersection. To fix the product, first join all authorized,
currently-visible source-attested field sets under a bounded search budget,
then choose at most K=5 *complete* fork candidates by an independently
evaluated ranking policy. Do not silently raise K, expose intermediate
overflow arm identities/counts, return an exhaustive oracle as the product
path, or rename this regression a measured E2 improvement.

## Non-claims

**No genuine publisher-authored tasks, no independent held-out query/route/field/permission gold and no real external-agent utility**. The aliases, fields, source contracts and expected topology were developed locally. This cannot confirm arbitrary deeper/fan-in joins or row identity, calibrated overflow ranking, production p95, service level, real API latency, data privacy outside the shown source policy, or actual tool execution. Benchmark-only exhaustive matching must **never become the product query path**.

Preserve #1535 and #1560 OPEN, #1346 source-independent benchmark intake and #1477 paired agent E2 as separate gates, #1356 v0.18 release HARD HOLD and frozen #432/#424 negative artifacts unchanged.

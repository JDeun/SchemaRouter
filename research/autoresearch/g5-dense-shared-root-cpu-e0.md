# G5 same-root fanout CPU study (synthetic E0, NOT E2/SLO)

## Why
The existing opt-in source-native shared-root G5 benchmarks primarily sample
sparse one-fork 500/5000 catalogs; PRs #1694–#1696 introduced bounded
source-root and consumer-ID sharding for more than 32 native one-hop paths.
Without explicitly measuring dense cohorts we cannot reason about their
CPU/wall overhead or the effect of live availability restrictions.

## Preregistered source-only scenarios
Reuse `build_fixture` with **500 / 5,000 original native registered routes**
and add **33 / 64** extra registered status consumer routes, each binding
the SAME original typed scalar `crm.fork_customer_id` root as the owner.
Total catalog sizes are therefore **533 / 564 / 5,033 / 5,064** native routes.
The developer-only original registry scanner is limited to this fixed
one-root/two-leaf topology and finds exactly 34 / 65 authorized complete
forks. No benchmark reference is passed into the native product index.

For each size/density, build the canonical native index once; record its
build time separately. With all routes healthy, *every* complete fork is
authorized but public K5 cannot rank 34/65; correct outcome is
`over_k_unranked`, zero exposed candidate IDs. With the SAME graph,
principal and snapshot, dynamically mark all 33/64 extra status routes
unavailable; one original fork remains and must be returned. Every query
runs the existing two-arm source/policy/availability rechecks and uses
three preregistered exact EN/KO/JA host-declared aliases.

Report **20 warmed per-condition** Linux CPU/wall observations for all four
workloads (3 unmeasured warmup checks, p50/p95/p99/mean), separated
from one-time index-build cost, plus process peak RSS. No silent K increase,
gold-aware refill, source/tool executor, authorization grant or default
routing change. The benchmark report is aggregate metadata only.

## Bounded indexed pre-fork scheduling A/B (#1700, E0)

The follow-up skips one redundant complete >32 source-validated witness scan by
scheduling canonical *indexed* consumer route ID shards upfront only when:
a single original source root, private budget >=16 and 33..128
structural consumer route IDs. Live availability remains a mandatory
per-shard check, including the default snapshot health callback. The scheduling
set is NEVER authority or a result. EVERY shard still runs the original
authorization/field-scope/type/pinned-fingerprint/availability and late
binding validation, and both complete arms are collected twice before any
candidate/count disclosure. Public strict K5 and execution rights are unchanged.

Developer A/B runs on the same ephemeral Linux runner: original private
per-arm >32 scan then split versus bounded index-only prepartition. Both
conditions use the same native 500/5000 base + 33/64 same-ID status leaves,
same strict K5 over-K and live health-withdrawn baseline. Each is a separate
fixture build, run in a fixed noninterleaved order with 20 warmed samples.
Therefore this is NOT a controlled causal benchmark, stable hardware SLO,
independently reviewed publisher gold or E2.

The one-index differential regression counts private authorized arm calls
(33: old 8, new 6; 64: old 12, new 8), compares exact source candidates and
abstention under the same original index and forbids private IDs. Even
with a live availability predicate, the SAME original callback runs in every
typed source-checked leaf; this may incur extra work after most paths are
revoked, and is reported separately in the A/B results rather than hidden.
When test-only shard budget is too small, the original path remains in use
to avoid a new false refusal.

## Non-claims
These are **developer-authored synthetic CRM graphs**, not independent
publisher task/gold/permission labels, runtime business responses,
external-agent E2, real no-fit calibration or production capacity/SLA
measurements. Kernel scheduling, runner hardware, fixture topology and
authorization density limit performance generalization. Do not invent a
latency target or lift #1356 HARD HOLD based on synthetic CPU values.

Keep #1535/#1560 OPEN, #1346/#1477 independently source-owned E2
BLOCKED_EXTERNAL and frozen #432/#424 historical negatives unchanged.

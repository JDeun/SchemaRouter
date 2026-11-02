# B1 mixed-source catalog churn parity — E0 design (2026-10-26)

## Purpose and boundaries

The original Algorithm 1 B1 checklist still requires versioned 500/5000-route
heterogeneous catalogs under source churn, principal scope, and live availability.
Static 500/5000-source exhaustive-oracle parity already exists. Extend its
research-only audit using the **same** registered native ToolSpecs, original
policy and field proof, built-in InMemoryRegistry source journal, and canonical
NativeSchemaGraphIndex. No new product index, planner, agent, executor, or
model-derived authority is introduced.

## Approach

Preferred: deterministic reversible mutation of one original source contract
(license revoke, then restore), checking that prior index versions fail closed,
  that each journal-refreshed snapshot has the same identity, posting manifest,
  and authorized outcomes as a full graph-index build, and that original
  source-scanning oracle results match independently declared expected routes
  under all four policies and EN/KO/JA aliases. Also change policy,
principal, and a **same-object** live availability predicate without changing
the source revision to detect permission/health caching.

Alternatives ruled out: synthetic status-only mocks (no original-source path)
and a second runtime index (duplicates source authority and product routing).

## Contract

- Exact catalog sizes: 500 or 5000, fixed four mixed source families.
- Revocation must remove the OpenAPI match, while restoration must return it.
- Source schema changes must reject queries through the old index before
  journal refresh; updated journal index equals rebuilt index in source
  snapshot ID, indexed count, original oracle and public route sets.
- Independently update authorized policy and a mutable health set without
  touching the registry version; outcomes must immediately reflect changes.
- Include an unprivileged principal in indexed-vs-source checks; never emit
  source data, case IDs, route IDs, or model-claimable E2 quality evidence in
  published aggregate JSON. Aggregate timing, CPU, and process RSS are E0 only.
- Reject non-built-in/non-versioned registries via existing refresh guards.

## Limits

These source endpoints exercise **direct postings**; the synthetic fixture's
canonical graph has no producer→consumer dependency edges. Graph identity
comparison here does not qualify nonempty graph-edge incremental churn (that
requires separate source-typed dependency fixtures and external E2).

This exercises developer-authored native-like registered contracts, not
independently collected source/provider catalogs or owner-signed gold. It
does not establish actual production churn throughput, token/schema bytes,
learned ranker quality, no-fit accuracy, or E2 task completion. Preserve
#1346/#1477 BLOCKED_EXTERNAL, Draft #1755 and #1356 HARD HOLD.

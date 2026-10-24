# OPTIMADE Source Contract E0 Plan

**Goal:** Distinguish host-reviewed OPTIMADE source identity, record IDs, source units, and canonical units without granting execution authority.

## Design

- Pin the original discovered ToolSpec fingerprint and versioned base URL before review.
- Restrict the reviewed ToolSpec to one selected entry type and its search/get endpoints.
- Require host-declared semantic IDs, a license declaration, and exact source-unit declarations.
- Permit conversion only through a host-supplied UnitNormalizationSpec; provider annotations never supply conversion factors.
- Keep GET record IDs required, bounded, path-located, and closed-schema.
- Reject a response whose ID or entry type differs from the requested record.
- Let Algorithm 1 select the explicitly approved input root only when every required field is visible and semantically/unit compatible. Without a host ID, return a typed call with a missing argument, not a guessed value.

## Verification

- The source copy remains unchanged after review; repeat review and source fingerprint drift fail closed.
- Unrelated entry types and global license metadata do not leak into the reviewed ToolSpec.
- Wrong/missing source units, conflicting identifier semantics, and unreviewed unit annotations are rejected.
- English/Korean/Japanese aliases produce the same typed plan.
- Mocked GET verifies record identity and standard-executor unit conversion.
- Native host-root proof accepts only a closed required scalar ID schema; public K5 and default routing remain unchanged.

## Limits

This is E0 source-contract work. It does not prove independent provider provenance, live interoperability across providers, scientific correctness, measured answer quality, or independent E2. Keep Draft PR #1748 and v0.18 release HOLD.

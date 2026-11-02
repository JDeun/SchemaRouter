# B1 prepared field-routing session refresh — design (2026-10-27)

## Purpose and non-goals

Continue the approved #1560 / #1771 provider-neutral schema-router product:
an application must be able to update its prepared field-only route index
after a native registry schema change without inventing a new provider adapter
or executing provider data queries. Existing immutable sessions remain stale
and fail closed. No default promotion, ranking quality or E2 claim.

## Considered approaches

1. Re-run `prepare_field_routing` after every update: safe but forces an
   exhaustive native scan, wasting the already implemented B1 source-owned
   posting + G5 journal deltas.
2. **Selected:** return a new session through `SchemaFieldRoutingSession.refresh`,
   reusing the existing canonical `NativeSchemaGraphIndex` delta paths.
   Auto journal refresh is supported only by the exact built-in InMemory and
   SQLite registries. Other registries need an explicit changed-key tuple,
   checked against the entire native source fingerprint manifest. No update
   of the old session or new cache/graph engine.
3. Background refresh tied to registry writes: wrong lifecycle and authority
   boundary for the current opt-in application-owned API.

## Invariants

- No refresh of a version that did not change, wrong source, expired journal
  or forged/omitted changed-key list; never silently fall back to a scan.
- Preserve detached owner-review catalog and approved host roots. Refuse
  source-policy mutation during refresh, fail closed on missing host roots.
- Resulting immutable session must match a newly prepared current-source
  session for direct and typed dependency FieldGroup outcomes; the original
  session remains invalid after source revision.
- No model inference, remote network requests or provider data invokers.

## Acceptance

In-memory and SQLite exact source journals; independent verified-hint refresh;
wrong hints, no-change and policy/source drift refusal; 500-route parity,
no source `tools()` full scan in journal path, provider execution never called;
existing default retrieval behavior unchanged. Protected full CI remains a
separate integration gate.

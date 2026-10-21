# M1 #1560 — SQLite transactionally persisted mutation receipts (E0)

2026-10-21, engineering-only. Extends merged #1671's source-owned
in-memory change journal to SQLite without implying a production
fast-index read boundary.

- The optional table `schemarouter_registry_mutations` records
  `version INTEGER PRIMARY KEY` plus a compact JSON list of **only
  sorted native tool keys**. Every successful SQLite register,
  compare-and-swap replace, unregister, CAS delete, atomic batch
  unregister, mixed restore, batch CAS upsert and batch upsert inserts
  the mutation record in the SAME `BEGIN IMMEDIATE` transaction as
  ToolSpec persistence and logical version bump.
- Transaction rollback, failed collision/stale CAS and empty batch
  publish neither new registry version nor mutation record. Persistence
  and reopen/cross-connection reads are tested using the actual SQLite
  database; a read uses its own SQLite snapshot transaction to pair
  the version with exact continuous mutation rows.
- Journal rows retain only 256 mutation versions. A read of more than
  64 distinct keys (across batch/window) fails closed. Existing batch
  writers with >64 keys still succeed, but commit a **NULL barrier**
  instead of a dishonest incomplete change set. Readers reject
  missing, expired, oversized, duplicate, malformed or altered rows;
  they must full-rebuild their native index.
- Existing databases opened after the upgrade create the optional
  mutation table without changing their logical version. Old edits
  have **no fabricated history**; reading from before the first
  recorded version fails closed. The validated historical legacy
  migration path also initializes the optional table transactionally.

**API boundary:** `SQLiteRegistry.changed_tool_keys_since` exposes
a bounded data-minimized receipt for engineering research. It does
NOT give authority to execute a tool, grant principal access or bypass
the canonical source scan. The fast path
`NativeSchemaPostingIndex.refresh_from_inmemory_journal` in #1672
explicitly accepts the exact built-in **InMemoryRegistry**, not SQLite;
a cross-connection/legacy-database trust audit must occur before any
SQLite indexed fast refresh can skip verifying all native source
fingerprints.

This E0 proves no production 500/5000 route p95/p99 win, no
cross-process exactly-once consumer cursor persistence, independent
provider-native gold/E2, no-fit calibration or v0.18 readiness.
#1560/#1535 remain open; frozen #432 and #1356 HARD HOLD unchanged.

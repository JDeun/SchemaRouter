# #1560 — explicit SQLite-source mutation journal posting fast path (E0)

Adds `NativeSchemaPostingIndex.refresh_from_sqlite_journal(previous,
registry)` only for the **exact built-in SQLiteRegistry** and only on
an opt-in research path. It uses the **same canonical immutable posting
delta assembler** as in-memory and full-scan `refresh`: the previously
built index, the original SQLite journal’s exact bounded
`from_version/to_version/changed_tool_keys`, and detached snapshots
of *only changed current tools*. It rehashes only those tools/endpoint
contracts, removing old routes of deleted/modified keys and assembling
the same SHA-256 snapshot/semantic scalar postings as a fresh full build.

The source-owned SQLite mutation table, persisted in the same original
BEGIN IMMEDIATE transaction as ToolSpec changes, was introduced in
protected PR #1673. A read obtains a consistent SQLite version+mutation
snapshot; expiration, missing records, oversized changes or malformed
journal bytes **fail closed**, requiring a new full snapshot. Both the
journal method and publishing step verify the exact live source
version, and original indexed lookup revalidates every candidate
against principal policy, availability, data scope and current source
fingerprints. Cross-connection concurrent mutation, batch, add,
replace, remove, transient add/remove, historical gap and malicious
malformed bytes have explicit tests.

**Trust boundary:** This accepts only SQLite files owned and mutated
exclusively through the audited built-in SQLiteRegistry API. If an
attacker or external application has direct write privileges to
`schemarouter_registry_tools`, `schemarouter_registry_meta` or
`schemarouter_registry_mutations`, they can forge a *valid-looking*
changed-key journal without a cryptographic signature. This research
fast path is **not** an authenticated cross-process audit ledger or
tamper-resistant journal; full rebuild is required for files with
untrusted non-registry writers. Startup policy that enforces exclusive
DB write ownership is **not** implemented by this PR. SQLite is not
enabled by default and no production optimization claim is warranted.

The G5 graph fast path in #1675 still accepts only InMemoryRegistry;
this PR does **not** authorize a SQLite graph refresh, model, tool
execution, source-independent E2 or release. Wall/CPU p95/p99 at
500/5000 routes, concurrent-live production writes and DB migration
deployment remain separate acceptance tests. Existing default lexical
routing and K5, frozen #432, #1346/#1477 evidence blockers and
#1356 v0.18 HARD HOLD remain unchanged.

**Current parent:** source-owned SQLite posting experiments are based on protected `7aae59452323483239957f234e0b2a099086fb6a` including merged original native graph PR #1675. Verify the exact new branch SHA with dedicated SQLite journal negative tests; prior-head CI cannot qualify a rebased PR.

# M1 #1560 — bounded in-memory registry mutation receipts (E0)

After #1669 native semantic posting and #1670 canonical graph edge delta
implementations, both still require a full current-tool fingerprint
manifest check. To remove that cost without trusting caller change lists,
we must first own source mutation history under the registry's atomic
write lock.

This **partial E0** implementation adds `RegistryMutationReceipt` and
`InMemoryRegistry.changed_tool_keys_since(from_version)`. Every
successful single insert/replacement/deletion, CAS, batch, rollback and
restore now commits its changed keys in the SAME `RLock` critical section
that advances the registry version. Unsuccessful and empty writes create
no receipt. A reader atomically obtains `from_version`, `to_version`
and a deduplicated, lexically ordered set of changed *tool keys only*;
no original schemas, field names, principal scopes, credentials, query
text or tool fingerprints enter the journal.

History is bounded to 256 mutation versions, with a maximum of 64
distinct returned keys. Gaps, expired/future/invalid cursors and oversized
deltas fail closed with `RegistrationError`, requiring a full fresh
build instead of claiming a complete delta. It never takes authority
from this receipt to execute or publish a graph path. The registry is
not an authenticated publisher, and subsequent mutation after the
receipt requires a consumer's final exact-version recheck.

**Important:** SQLiteRegistry is explicitly **not** covered by this
change. Persisted journal storage, cross-process/cross-connection
transaction validation, migration/rollback and read limits need their
own tests before any SQLite receipt can be trusted. Nor does this PR
yet change `NativeSchemaPostingIndex.refresh` to skip all-tool
fingerprint verification. Existing full verification and strict-K5,
principal RBAC/data scope/availability and fingerprint checks remain
the default. No production p95/p99 or publisher-independent E2 is
claimed, and #1560 and v0.18 release HARD HOLD remain open.

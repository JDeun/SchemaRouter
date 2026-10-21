# M1 #1560 — in-memory source-journal fast posting refresh (E0)

**Stacked on #1671's in-memory atomic changed-key receipt** and the
previously merged canonical #1669 posting-delta rebuild.

A separate explicit opt-in method
`NativeSchemaPostingIndex.refresh_from_inmemory_journal(previous, registry)`
only accepts the **exact built-in InMemoryRegistry type**, not arbitrary
ToolRegistry proxies/subclasses, SQLite or another registry implementation.
It consumes the registry-owned `changed_tool_keys_since` read under the
registry mutation lock, including its `from_version`, `to_version` and
bounded changed tool keys. It reconstructs the current source fingerprint
manifest by reusing unchanged fingerprints from the previously pinned
snapshot and querying only the changed keys (including deletions).

Both this journal method and the older conservative full-scan
`NativeSchemaPostingIndex.refresh` use the SAME canonical delta posting
assembler: original endpoint fingerprints and semantic scalar contracts
are recalculated only for changed current tools; old matching routes are
removed; ordered postings and SHA-256 snapshot receipt maintain exact
full-`build` equivalence. All native source reads are detached snapshots.
Concurrent registry version changes after the receipt fail closed;
ordinary lookup independently requires an exact current source version
and principal authorization/data scope/availability.

No new interface on `ToolRegistry`; SQLite and custom registries must
continue using full-scan `refresh` or fresh `build`. A discarded
or expired journal cannot silently fall back to unverified fast update.
Unknown/no-change cursors are rejected. A transient tool added/removed
between index snapshots is accepted from the **authoritative** mutation
journal even if it appears in neither current nor old catalog.

E0 tests compare the fast path versus complete `build` snapshots,
EN/KO/JA analyst/viewer retrieval and typed source fields for add,
replace, delete, mixed batch and transient add+delete. Negative cases
include an alien source, empty delta, concurrent write injected into
changed-tool get, expired receipt; a forced observation spy proves the
fast path never scans `registry.keys()`/`tools()` and never calls
`get` for unchanged native contracts.

**Performance boundary:** copying the immutable snapshot maps and
sha256 canonical receipt remains O(catalog) memory/time, though the
number of ToolSpec copies/fingerprint recomputations is O(delta).
This is not an established production 5000-route p95/p99 improvement,
no SQLite/durable cross-process journal, and no atomic unit-of-work
execution protocol or provider-owned source E2. The one-hop graph
refresh still scans the complete fingerprint manifest for safety:
`NativeSchemaGraphIndex.refresh` fast-journal adoption must be
separately reviewed and tested. No default lexical retrieval, source
authorization, K5/ranker, frozen #432 or release HOLD #1356 changes.

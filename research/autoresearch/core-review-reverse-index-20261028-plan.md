# B1 Reverse Route Field Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index native route→semantic review candidates once per source revision instead of scanning all postings on every principal review page.

**Architecture:** Extend the immutable native posting snapshot with a reverse route map, ordered route IDs and old-format opaque cursor anchors; maintain them at full and incremental build. Reuse them in the review-first session with a binary-search seek while leaving all original live authorization and double reattestation intact.

**Tech Stack:** Python 3.12, pytest, Ruff, Pyright, standard `bisect` and `hashlib`.

**Spec:** `research/autoresearch/core-review-reverse-index-20261028-design.md`, issue #1795.

## Global Constraints

- No model, provider executor or separate index engine. No semantic inference.
- Retain source `snapshot_id`, `sr1:` cursor ABI, exact principal guards and page budgets.
- Verified journal refresh must remain source-owned; no page-triggered `tools()/keys()` scan.

## Review Focus

- An endpoint with two different semantic field IDs appears **once** in the ordered route list, with both IDs retained.
- Native tools with missing source/license or no scalar semantic field must not receive review route anchors.
- A source revocation/deletion and later restoration must rotate cursor anchors, preserve forward/reverse parity and reject stale cursors.
- Unicode, control-character and 270+ character route names must preserve fixed cursor length without name parsing or private source disclosure.
- Availability/policy/data-scope mutation across a page must fail closed even with the accelerated iteration path.
- The indexed `sr1:` lookup must not expose the existence of a guessed private
  route: live principal visibility is mandatory on the anchor itself.

### Task 1: Canonical reverse map and source-version cursor anchors

**Files:** `src/schemarouter/native_semantic_index.py`, `tests/test_native_semantic_index.py`, `tests/test_sqlite_native_posting_journal_e0.py`.

**Interfaces:** `NativeSchemaPostingIndex.route_semantic_ids`, `.review_route_ids`, `.review_cursor_anchors`; `_native_review_cursor(snapshot_id: str, route_id: str) -> str`.

- [x] Step 1: Add RED 500/5000 source/semantic intersection, duplicate route, invalid/no-source route and in-memory/SQLite journal delta tests, using independent literal fixture expectations.
- [x] Step 2: Run exact tests RED on missing index properties.
- [x] Step 3: Fill new immutable derived index fields in both full build and original verified delta assembler; keep original receipt/snapshot formula unchanged.
- [x] Step 4: Run index tests GREEN, source journal parity, Ruff and Pyright.

### Task 2: Wire public principal-safe page seek

**Files:** `src/schemarouter/field_routing_session.py`, `tests/test_schema_field_routing_session.py`, `README.md`, `examples/schema_only_field_routing.py`.

**Interfaces:** Existing `inspect_visible_fields(...,after_route=None,limit=32)` unchanged; `sr1:` cursor unchanged, but `postings.items()` and global sort forbidden on page requests.

- [x] Step 1: Add RED behavior tests with `postings.items()` trap and 5000 original routes; existing current-principal, cursor, UTF-8, hidden data and stale-source tests remain acceptance cases.
- [x] Step 2: Verify RED on per-page global inversion.
- [x] Step 3: Seek `review_route_ids` by bisect/cursor map and attest originals; do not copy the whole remaining route tuple.
- [x] Step 4: Run session/G5/index tests GREEN, example, repository Ruff, changed-file Pyright, and attempt entire project suite.

### Task 3: Performance evidence and GitHub handoff

**Files:** `scripts/benchmark_native_review_pagination_b1.py`, new test as appropriate, `research/autoresearch/paper-toolcall-implementation-e0.md`, benchmark evidence.

- [x] Step 1: Create a source-neutral 500/5000 route benchmark using real session pagination, p50/p95/p99 per-page wall time and bounded output bytes; assert total page coverage/unique IDs, no records or LLM.
- [x] Step 2: Run benchmark and record environment, sample counts and provenance without claiming independent quality or p95 improvements without baseline.
- [ ] Step 3: Commit, independent review, correct Important issues with RED→GREEN, publish Draft stacked on #1794, and track exact-head CI. Keep #1560/E2/release gates open.

# Original Algorithm 1 A6 Source-Byte Intake Implementation Plan

> **For agentic workers:** use TDD and the existing native E2 intake script.

**Goal:** Bind submitted exact original provider inventory bytes to existing
unscored source/manifest/case/gold/DEV claims, without manufacturing gold.

**Architecture:** `inspect_unscored_native_cohort` owns original v1 validation.
The new opt-in wrapper first checks raw inventory bytes and digest, then
calls the existing validator, returns a sanitized incremental boolean, and
retains all external qualification gates. The CLI accepts an optional fifth
path but no raw source data appears in stdout.

**Tech:** Python 3.12, pytest, Ruff, Pyright, original CI workflow.

## Task 1 — strict source byte binding

**Files:** `scripts/inspect_independent_native_e2_intake.py`,
`tests/test_independent_native_e2_intake.py`.

- [x] RED: a source-matching snapshot produces only a structural-only report.
- [x] RED: one-byte source drift, forged declared digest, no bytes, wrong type
  and >5 MiB refuse without leaking source content.
- [x] GREEN: implement additive fifth-stream wrapper and CLI path while
  retaining existing unscored four-file behavior.
- [x] Ran native-intake and adjacent scoped-agent synthetic tests, repository
  Ruff, and targeted changed-script Pyright successfully; same-head PR CI
  qualification still follows after Draft publication.

## Task 2 — evidence and handoff

**Files:** `research/autoresearch/independent-native-e2-intake-preflight.md`,
`research/autoresearch/paper-toolcall-implementation-e0.md`, Draft #1755,
issue #1560.

- [x] Document locally bound bytes vs unverified third-party identity.
- [ ] Record red→green, test counts and exact HEAD/CI without checking A6
  until actual independently authored reviewed fixtures are received.
- [ ] Keep Draft, external E2 blocks and v0.18 release HARD HOLD.

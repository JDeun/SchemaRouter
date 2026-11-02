# A6 per-case source-witness E0 implementation plan

> **For agentic workers:** test-first extension of the existing native intake;
> retain four-/five-file compatibility and all external qualification holds.

## Task 1 — strict witness-byte source pairing

**Files:** `scripts/inspect_independent_native_e2_intake.py`,
`tests/test_independent_native_e2_intake.py`.

1. RED: complete 3-language × 5-kind synthetic publisher-style case set
   supplies per-case native-authority and gold bytes, validates both distinct
   digest fields and returns structural-only flags.
2. RED: missing, duplicate, foreign case, wrong digest, cross-paired witness,
   empty/noncanonical base64, malformed JSON and size overflow fail closed.
3. GREEN: add `inspect_witness_pinned_native_cohort(...)` wrapping the existing
   five-source-byte preflight and case/gold parser; no second scorer.
4. GREEN: optional CLI paired `--native-authority-witnesses` and
   `--gold-reference-witnesses` arguments; require exact prior source snapshot.

## Task 2 — close integration and evidence boundaries

**Files:** `.github/workflows/research-independent-native-intake.yml`,
`research/autoresearch/independent-native-e2-intake-preflight.md`,
`research/autoresearch/paper-toolcall-implementation-e0.md`.

1. Extend the existing native source intake workflow with the full A6
   witness-byte negative and positive tests, not a second unconditional CI.
2. Update the private file contract and exact command examples; never put
   publisher originals in GitHub or output reports.
3. Verify original four/five-file backward compatibility, focused + broad
   regressions, repository Ruff and targeted Pyright, then publish as a
   single A6 feature continuation on Draft PR #1755 using safe expected-SHA.
4. Check latest remote commit workflow results, update issue #1560 and Draft
   #1755 notes; **A6 E2 checkbox remains open** until provider signatures,
   permissions, independent gold and actual original evidence are supplied.

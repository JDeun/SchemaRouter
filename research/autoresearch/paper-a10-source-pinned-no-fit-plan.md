# A10 source-pinned no-fit E0 implementation plan

**Goal:** Provide a reusable actual evaluator, not a filled-in false E2 result.

## Task 1 — fail-first source-bound score contract

1. Write `tests/test_research_paper_no_fit_calibration_a10_e0.py` with
   independent synthetic manifest/gold/native bytes and observed statuses.
2. Run RED pytest (missing evaluator).
3. Implement `scripts/research_paper_no_fit_calibration_a10_e0.py` strictly
   wrapping existing byte-source intake; classify statuses by the existing
   paper decision mapping, report only aggregate by-language metrics, and
   protect sources and input shape.
4. Run GREEN focused tests.

## Task 2 — qualify limitations and integration

1. Add schema/denominator and disclosure abuse regressions and a CLI mode
   that reads explicit paths without printing original bytes.
2. Include focused module in existing original-paper research CI workflow.
3. Update central Algorithm 1 checklist: implemented E0 scorer, external
   independently reviewed gold still blocked and A10 E2 remains unchecked.
4. Run targeted suites, Ruff and compilation; verify exact remote HEAD before
   publishing to existing Draft PR #1755, check latest-head CI and preserve
   #1346/#1477/#1356 external/release gates.

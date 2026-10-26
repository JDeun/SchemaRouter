# A8 Understood native direct >K E0 integration plan

Date: 2026-10-26. Issue #1560. Stacked Draft #1755.

## TDD / implementation

- [x] RED: no paper Understand→native research-ranker adapter exists.
- [x] GREEN: preserve original compiler's `over_k_unranked`; new
  explicit opt-in returns a separately labelled source-only E0 shortlist.
- [x] RED→GREEN: actual query rather than canonical group alias goes to
  ranker; only current original principal-visible/typed/authorized routes
  are offered, with exact five distinct source offsets.
- [x] RED→GREEN: named before-K tool filter, 32-candidate hard cap,
  unknown tool/source mismatch, malformed model selection and callback
  mutation of catalog/policy/hints/view all fail closed.
- [x] Local Python 3.12: new **12/12** source-safety tests; **190/190**
  focused paper/native regressions. Whole-repository Ruff and changed-script
  Pyright **0 errors/0 warnings**; exact-head remote CI still required.
- [ ] Publish code + tests + workflow to stacked Draft and qualify its exact
  GitHub Actions head.
- [ ] Update issue, PR and canonical handoff with confirmed CI evidence.

## Full A8 remains open

- [ ] Externally justified ranker/tie policy and preregistered independent
  EN/KO/JA/OOD gold, Recall@5 and no-fit error measurement (#1346).
- [ ] Actual provider-and-agent paired performance, costs and p95/p99
  under the identical authorized source snapshots (#1477).
- [ ] Catalog-wide >32 ranked discovery and 500/5000 churn/parity (B1).

The new code never introduces a default ranking policy or a trustworthy
quality label. Release/default promotion #1356 stays HARD HOLD.

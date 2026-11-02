# A5 OPTIMADE live E1 — implementation plan

1. RED: write full HTTP mock end-to-end, stale fingerprint, wrong source
   identity, model-forged input and denied authorization tests.
2. GREEN: compose existing OPTIMADE source adapter, immutable fingerprint
   review and original bound native executor into opt-in SDK registration.
3. GREEN: add a two-phase keyless COD pilot (`probe` → pinned `run`) using
   one host-owned search identity as the A5 get argument. Keep only host-only
   tool receipts; print bounded non-sensitive summary.
4. Run scoped pytest, Ruff, Pyright, historical A5 tests and optional COD
   live. Review failures and keep the main release gates unchanged.
5. Update canonical resume document, open one GitHub issue, publish a stacked
   Draft PR against #1762 with explicit CI and E2 limitations.

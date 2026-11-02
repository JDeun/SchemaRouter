# Crossref native A5 E1 — execution plan

1. RED: tests for the exact original curated nested-field contract, a
   fingerprint-pinned opt-in registration, host-bound A5 ToolCall to a real
   HTTP mock, identity/schema failures and denied access.
2. GREEN: reuse existing projection, semantic attestation, native HTTP
   invoker and native A5 E1 direct bridge; introduce only a Crossref-specific
   reviewed registration and response-identity guard.
3. Add a deterministic keyless `probe` + pinned `run` CLI, scoped CI with
   manual live execution and resume notes.
4. Verify original-paper and adapter regressions, format/type checks, and
   optional live request. Review and file one issue plus stacked Draft PR;
   keep E2 and downstream publication claims explicitly unverified.

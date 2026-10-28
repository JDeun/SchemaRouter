# #1775 — Prepared schema-only structured Understand(q) wiring

## Intent and owner boundary

The library should answer **which registered schema fields and parameters a
question needs**, not fetch rows. Existing original-paper `PaperUnderstanding`
and direct/named graph P2 compilers already validate host-reviewed intent and
concept contracts; `SchemaFieldRoutingSession` cannot yet use them. Connect
those components through the reusable prepared session, without adding any
provider adapter, executor, or built-in model invocation.

## Options considered

1. **Reuse existing structured understanding + native graph proof (chosen).**
   Add `session.compile_understood(...)` and export the strict input contract.
   Preserves one engine, source-scoped proofs, cost and execution boundary.
2. Have the session call an LLM directly. This would require a separate
   reviewed source-disclosure surface, model budget, failure handling, and E2
   quality evaluation; it is a follow-on issue, not implicit in this wiring.
3. Add per-provider prompts / heuristics. Rejected because semantics belong
   to registered owner contracts and providers vary by user.

## Contract

- `SchemaFieldRoutingSession.compile_understood(understanding,
  *, principal, intent_registry, host_source_arguments=None, k=5,
  max_hops=2) -> PaperTypedToolPlan`.
- Input `PaperUnderstanding` is **untrusted**: only owner-declared concept and
  intent IDs can form the semantic field requirement; model `parameter_hints`
  are never promoted into call arguments.
- `PaperIntentRegistry` is an explicit host-reviewed contract. The prepared
  index/catalog are reused and current authorization, data scope, fingerprint,
  provenance, exact K5 and source drift are enforced by the existing compiler.
- Direct and G5-supported 1-/2-hop results carry fields, typed parameter
  shapes and explicit dependency bindings. No source execution and
  `executable_authority=False` even for `status="ready"`.
- Existing `session.compile(query)`, `session.discover(query)`,
  `SchemaRouter.retrieve_authorized()` and all provider adapters are unchanged.

## Acceptance and evidence

RED→GREEN tests exercise direct host-root arguments, one-/two-hop typed
bindings, ignored forged model hints, denied/stale sources, invalid intent and
strict bounds, and absence of data execution. Update public exports, example,
README and the canonical development-resume note; keep Draft and release HOLD.

**Out of scope:** model accuracy / independent `Understand(q)` semantics,
automatic transcription/translation, provider data fetching, executable
tool calls, and answer synthesis.

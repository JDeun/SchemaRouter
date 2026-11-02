# A5 OPTIMADE native live E1 — design (2026-10-27)

## Gap and boundary

The original A5 E1 direct bridge already performs a typed P2 proof, scoped
agent selection, host-owned argument binding and dispatch to the existing
registered native executor. OPTIMADE's discovery adapter and explicit host
review function also exist, but an independently usable **discovery →
fingerprint check → host review → bound publication → A5 execution** path
was missing. Previous public live OPTIMADE evidence used host-selected calls,
not the A5 route.

## Chosen design

1. Add an opt-in SDK registration helper which discovers an OPTIMADE source
   using the existing adapter and supplied HTTP/network policy. Require an
   externally pinned *unreviewed* discovery fingerprint, versioned base URL,
   reviewed license label, field semantics and entry identifier semantics.
   A source-declared `string | null` field with `x-optimade-type` is not an
   unconditional scalar P2 match. A prior host review may expressly require
   a **strict runtime non-null string refinement** for that pinned field.
   Only source types `string` or `string | null` are accepted; the reviewed
   output shape is narrowed and execution rejects null. The original source
   schema remains in the review provenance. This conditional requirement
   does **not** assert that every source record is non-null.
2. Reuse `review_optimade_paper_tool` and bind **the same discovery invoker**
   to the reviewed ToolSpec with `SchemaRouter.add_bound_tool(replace=False)`.
   Never auto-approve schema fingerprints, issue broad CRUD grants or substitute
   a synthetic invoker.
3. Add an opt-in COD research runner with `probe` and `run` phases. `probe`
   makes discovery GETs and prints an unreviewed fingerprint; `run` requires
   that exact fingerprint, uses one fixed host-selected, source-filtered
   OPTIMADE search to acquire an actual source ID, then routes the resulting
   host ID through the *existing* A5 direct native bridge. A scripted model
   and agent make this a reproducible E1 wiring check, not an E2 test.
4. Keep the raw discovered license **unverified**: the host label is a
   research restriction, not evidence of redistribution/commercial rights.
   Assert response ID and **exact GET/search formula agreement**; fail on
   schema, null, ID, authorization or provider drift. Never fabricate data.

## Rejected alternatives

- Hardcode COD schemas or self-approve the latest fingerprint at run time:
  source change could silently widen a model-visible capability.
- New A5 HTTP executor: duplicates registered native dispatch and security.
- Treat search-result identity as a model-provided argument: bypasses the
  trusted host materialization invariant.

## Acceptance

- Full mock-transport discovery, publication, host search and A5 typed call;
  forged model ID cannot reach provider; source record/selection verified.
- Fail before publication/tool execution on stale fingerprint, incompatible
  schema or missing reviewed output; incorrect get identity is rejected.
- Real keyless COD attempt separately labeled as live if reachable. No
  independent E2, source license verification or product release claim.

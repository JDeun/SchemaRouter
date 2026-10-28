# B1 owner review of source-typed input parameters — design (2026-10-27)

## Gap and decision

Issue #1791 follows #1789: review-only `SchemaFieldRoutingSession` pages expose
principal-visible native output field semantics, but omit the *input parameter
shapes* that Algorithm 1 P2 later needs to construct a typed call. New owners
can inspect output field requirements before approving their concept catalog,
but not the inputs of those exact routes.

Use the existing `PaperPlanParameterMeta` and `_paper_public_parameters` typed
projection (already used by the guarded compiled plan). Include a bounded
`parameters_meta` tuple in each eligible `SchemaFieldReviewRoute`. Do not
create a new registry, parameter inference/alias mapping or execution engine.

Alternatives considered: (1) expose raw `ParameterSpec`/JSON schema, rejected
because it includes untrusted annotations and wire metadata; (2) require a
catalog and compile a route just to see its input parameters, rejected because
it reintroduces the review-before-approval cycle; (3) reuse the existing
principal-scoped plan projection in review pages, selected for parity and
minimal disclosure.

## Safety and behavior

- Only already-eligible, principal-authorized read-only source routes with
  visible source-attested semantic output fields are reviewed. Parameters
  originate in the same current `_data_scope_endpoint_view` as those outputs.
- Return only canonical parameter name, required flag, location and safe basic
  JSON type labels, never descriptions, aliases, header wire names, defaults,
  schemas, supplied values or credentials. Scoped denied output field aliases
  cannot be echoed by a parameter name.
- Maintain 512 parameters per route and 2048 per page, inside the existing
  conservative 256 KiB page budget; fail rather than partially exposing an
  overwide registered route. Count UTF-8 bytes for each projected attribute.
- The existing double re-attestation must cover parameter projection as well
  as outputs. Registry fingerprints, source/policy/principal witnesses and
  availability rechecks remain authoritative, and errors are sanitized.
- Owner approval stays explicit, routing remains K5 and opt-in, no provider or
  model data call is made. This is not qualified E2, trained ranking or an
  executable receipt. #1346/#1477 and release #1356 remain gated.

## Protected-CI follow-up: stand-alone model entrypoint

Introducing `catalog=None` for the review-first bootstrap also widened the
static type of `session._catalog`. The separate, public-module
`compile_model_query(session, ...)` still accessed that optional attribute
directly, bypassing the session's explicit review-only guard. The existing
exception handler happened to turn the resulting `AttributeError` into a
generic refusal, but Pyright identifies three unsafe optional uses and the
function did not enforce the canonical approved-catalog contract itself.
Require `session._require_catalog()` before owner declarations or any model
disclosure, preserving the pre-existing authorized path. This is an inherited
core gate/typecheck repair, not a new model policy or output capability.

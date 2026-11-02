# Original A5 Crossref native E1 — design (2026-10-27)

## Missing wiring

The built-in Crossref HTTP/JSON profile exposes `get_work` and the native
invoker executes it, but its declared output is only the opaque `message`
object. Original-paper typed P2 cannot prove `paper.doi` and
`paper.publisher`, so an A5 agent cannot obtain an approved typed route from
this unmodified provider. The generic native executor **already** handles
`FieldSpec.path` and flattened `result_path`; no new projection engine is
needed.

## Chosen implementation

1. Add native scalar `message.DOI` (identifier) and `message.publisher` fields
   to the curated `get_work` response contract. Retain its historical
   `message` object field, and narrow the nested output-schema properties to
   the fields the source declares. Source: Crossref's REST API
   (`https://www.crossref.org/documentation/retrieve-metadata/rest-api/`),
   singleton `GET /works/{doi}`.
2. Expose a **separate, opt-in** inspection + host-reviewed registration API.
   Pin the curated **local declaration** fingerprint and official base URL
   from an earlier inspection step. Add source/license owner annotations and
   existing scalar host semantic attestations only after that check. The
   license is an **unverified research restriction**, not a commercial grant.
3. Publish the attested tool with the **existing** prepared HTTP/JSON native
   invoker via `SchemaRouter.add_bound_tool` under the current router network
   policy and principal authorization. Wrap only Crossref's singleton read to
   refuse provider DOI identity mismatches, absent/ill-typed publisher and
   malformed Crossref envelopes (including non-singleton `message-type`)
   before the native ToolResult is published.
4. Build a deterministic A5 E1 research runner (`probe`/pinned `run`): P2
   understands `paper.lookup` and proves required DOI/publisher contracts;
   the agent intentionally forges its DOI, but the native request uses only
   the bounded ASCII host-selected DOI (this opt-in pilot intentionally
   abstains on non-ASCII DOI strings). No extra search, generated DOI, alternate API key,
   simulated provider identity or independent E2 claim.

## Out of scope

- No automatic source review, guessed remote-schema freshness, license grant,
  LLM content validation or E2 autonomous evaluation.
- No change to default `router.add_provider("crossref")` access rights or to
  the generic executor. This curated descriptor extension changes only its
  discoverable schema; reviewed semantic edges remain opt-in.
- Real-network evidence must remain separate from mock-transport evidence.

## Acceptance

- A5 → host-pinned Crossref DOI → native `GET /works/{doi}` → typed,
  least-privilege DOI/publisher output, checked against the requested DOI.
- Stale declaration fingerprint, altered source schema, forged model DOI,
  identity drift, null publisher, unauthorized principal and unsafe DOI fail
  closed. No network calls for preflight failures.
- Dedicated scoped CI and optional manual keyless live probe/run, without
  treating the deterministic agent as independent E2.

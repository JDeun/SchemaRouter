# #1560 B1 E0 Heterogeneous Native-Catalog Parity Audit

Date: 2026-10-26. Scope: optional research harness on Draft #1755.

## Goal and boundary

Close the gap between prior 500/5000 mostly uniform noise measurements and
multiple original `ToolSpec` source types. Exercise the **existing** native
posting/graph index over 500 and 5000 registered endpoints in an explicit
synthetic source catalog containing OpenAPI-, MCP-, OPTIMADE-, and custom-like
tools, plus adversarial near-matches. An independent exhaustive registered
source scan is used **only by the audit**, never inside the indexed query.

## Approaches and decision

- **Chosen:** Keep source-native `ToolSpec` fixtures and reuse the existing
  `NativeSchemaGraphIndex`, concept retrieval and authorization code; audit
  typed field completeness from the original registry. This isolates B1 index
  parity without inventing an adapter parser or another routing engine.
- Rejected: add a second experimental index/router (would weaken source
  authority and duplicate the product path).
- Deferred: network-backed provider ingestion or externally labeled answer
  quality; these require separate source owner review (#1346/#1477).

## Acceptance

1. Exactly 500/5000 registered routes, bounded original source types, four
   source-disjoint single-endpoint concepts, and EN/KO/JA query aliases.
2. Actual indexed results equal the independent original-source oracle for
   visible matches, hidden output fields, unavailable sources, authorization
   denials, bad type/source/license near-matches. No invisible alternative
   name is disclosed.
3. A registered source schema mutation invalidates the old index and a
   rebuilt index reflects current source semantics; no stale results.
4. A reproducible CLI emits sample counts, exact-parity failures (failure
   closes the run), wall/process CPU p50/p95/p99, RSS and exact catalog size.
   No product-path exhaustive scan, extra executor, default ranking, release,
   provider provenance, or independent E2 claim.

## Limitations

All catalog records and task aliases are author-created E0 fixtures. They
do not authenticate OpenAPI/MCP/OPTIMADE upstream schemas or qualify actual
5000 heterogeneous real providers. Statistical summaries on small local
samples do not establish production p95/p99 SLOs. The B1 full acceptance,
external multilingual gold, and #1356 release remain blocked.

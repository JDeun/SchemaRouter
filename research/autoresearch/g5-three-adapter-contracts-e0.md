# G5 three original adapter compilers in one catalog — E0 compatibility only

Date: 2026-10-19. Owner: #1545 (M1), anchored to #1560 source-native indexed typed graph.

## What is and is not tested

Instead of inventing a second graph engine or relabeling generic synthetic ToolSpecs as native integrations, this no-network test invokes three original, currently implemented adapter compilers:

1. Original tool_from_openapi from a locally defined OpenAPI 3.1 CRM contact GET response document (produced string contact_id).
2. Original tool_from_mcp from an MCP tools/list-style read_case declaration with a real object-shaped required inputSchema and optional remote readOnlyHint annotation.
3. Original _tool_from_discovery from the installed OPTIMADE adapter, using an offline structures entry-info document (get_structures required string id with minLength=1, search_structures optional filters and server output projection).

The first two form one *host-reviewed* CRM contact_id-to-required-contact_id typed edge under the one canonical G5 index. All three are registered in the same InMemoryRegistry. Approved aliases are EN/KO/JA, but they are host-owned exact query aliases, not measured semantic translation or multilingual model success. The third is deliberately a different materials domain and must not become a G5 ontology root or create a CRM join.

## Security and provenance gates

- Original MCP readOnlyHint is NOT trusted to grant read-only execution authority. Explicit local host review changes its ToolSpec read_only flag; source license and semantic-ID declarations are also explicitly host supplied.
- Existing HostSemanticAttestation binds exact native tool and endpoint fingerprint, member name and type; it never creates an otherwise nonexistent provider parameter or output. A changed schema must invalidate old receipts.
- The original OPTIMADE get endpoint retains required id minLength=1. Current G5 _host_source_input_names permits only a strict, closed 1-4 scalar schema without this refinement; intentionally attempting to approve the OPTIMADE get as a source root must fail before any external request. There is no synthetic "success" from stripping the refinement.
- DataScopeRule makes contact_id hidden for a viewer, suppressing native graph evidence before K5, while the reader receives exactly one typed candidate.
- Registry revision invalidates the snapshot and blocks stale native graph evidence.
- Queries never execute original provider tools; no provider connections, MCP remote clients, OPTIMADE network calls, permissions or credentials are claimed.

## Exact limits and follow-ups (issue remains open)

This is adapter COMPILER contract E0 from local documents, not live transport E1 for OPTIMADE/MCP, not independent publisher-authored holdout, and not complete E2 agent task accuracy. Source fields and owner-reviewed semantic IDs are declared in the fixture, not independently verified against a real external provider. A single CRM typed join does not prove query-agnostic semantic integration across unrelated domains.

Next independent tasks are: license/source-pinned real OpenAPI/MCP/OPTIMADE provider snapshots with authentic original schemas and minimal host-reviewed grants; strict required-field and no-fit completeness across domain-disjoint original cases, per-language retrieval/false admission and CPU p50/p95/p99; practical constrained OPTIMADE ID input compatibility only if the host can preserve full provider JSON Schema and prove correctness; and paired external-agent E2 per #1346/#1477.

Do not convert E0 compiler tests or previous fabricated public demo E1 into commercial benchmarks. Historical original #432 negatives remain intact and #1356 v0.18 remains HARD HOLD.

# Gate B — discovery contract and scoped acceptance

2026-11-27. #1899 / #1897. [PRD](PRD.md) and [ADR-001](prior-art-and-adr.md).
Implementation frozen for the first Gate C comparison at [51744aa](https://github.com/JDeun/SchemaRouter/commit/51744aa15142a553e4ae6862ca5eea1c0f8421da). This is an isolated local engineering PoC, not a production release or measured agent-performance claim.

## Interface v0.1 (research)

Trusted host code constructs `Catalog(concepts, routes)`, using only the complete permitted schema surface. `concepts` maps a nonempty concept ID to a list of declared aliases. Each route carries source, tool, endpoint, sourceRevision, inputSchema, outputSchema and field annotations. Each annotation has a literal property-path array and provenance; optional concepts, identifier, groups, unit, sourceType, license. Paths are arrays, not inferred dotted-name nesting. Source descriptions and metadata are declared, not independently verified. The route identity is the tuple (source, tool, endpoint). The revision digest covers the entire permitted catalog and vocabulary. RDFLib stores the graph; SPARQL finds field-to-concept links. No LLM or inference engine is required.

```python
from historical_inventory import catalog, load_apis

# DEV historical logical schema inventory, not live native tool definitions.
index = catalog(load_apis())
result = index.discover([
    {"id": "modulus", "conceptId": "capability:bulk_modulus",
     "unit": "GPa", "sourceType": "calculated"},
    {"id": "papers", "concept": "research paper", "sourceType": "literature"},
])
```

Host/agent supplies already-understood requirements. Legacy list-of-string aliases remain usable. A structured requirement has a unique nonempty id and exactly one of concept (normalized alias) or conceptId (exact ID). Optional unit, sourceType, license are conjunctive exact strings on the **direct matching field**, not inference, conversion, license interpretation or authorization. Missing metadata cannot satisfy a specified qualifier. Ambiguous aliases return candidateConceptIds from the host-permitted vocabulary; qualifiers do not silently disambiguate a physical meaning. No fixed K; optional positive integer max_routes is a caller budget, applied in deterministic route order, not relevance ranking or optimal coverage.

### Result interpretation

- revision: snapshot digest. coverage: requirement ID to status; requirementResults: per-requirement receipt, normalized lookup concept ID when resolved, matchingRoutes, returnedRoutes, omittedRoutes, unsupportedProjectionRoutes, allMatchingRoutesReturned.
- matched: at least one returned direct field match, **not** proof of complete user-task coverage, all alternative tools, valid invocation, physical equivalence, or a cross-source join. allRequirementsMatched is true only for a nonempty set of requests each with a returned match. allMatchingRoutesReturned is separate.
- ambiguous / uncovered: multiple alias concepts or no eligible declared direct match; budget_limited: no returned match and at least one eligible route omitted by the budget; unsupported_projection: no returned match and eligible route(s) failed projection. Counts are relative only to the permitted catalog. An omitted or unsupported alternative may coexist with a matched requirement; counts expose this.
- views contain route, sourceRevision, full original inputSchema, projectedOutputSchema, fields, matches (direct paths per requirement), adjunctPaths (additional annotated fields), projectionPaths (selected path roots), and projectionKind=schema_view_only. Selecting an object root may retain its entire subtree, including unannotated properties. Ancestor descriptions and necessary definitions can also remain. Adjunct fields never establish another requirement match. Unit/license/source qualifiers do not filter contextual adjuncts or authorize disclosure.
- put/remove/replace_concepts validate then replace the graph and digest. Save writes a local Turtle snapshot; load checks reconstructed graph equality. No concurrent-writer, remote-store, cryptographic authenticity or production durability guarantee.

### Scope and schema constraints

The host must sanitize the **entire** permitted surface (including nested schema properties, definitions, descriptions, annotations, aliases, provenance and metadata) before creating a catalog. Queries do not grant access, perform dynamic per-field authorization, or redact a trusted full catalog. Keep separate host-permitted catalogs for different scopes; never expose internal snapshots or raw manifests as agent tools. The host independently validates tool execution, arguments and permissions. The historical inventory's 19 logical search routes are not verified native API invocation contracts.

The supported projection subset narrows explicit simple object-property ancestors, preserves input schemas unchanged, retains selected subtrees, identifiers and source-local groups, and includes necessary transitive local root $defs definitions. Only direct named local root definitions are supported (JSON Pointer ~0/~1 escaping); external/dynamic/alternate dialect/legacy reference scopes and unsafe projection ancestors are rejected. It does not implement general JSON Schema transformation, arbitrary nested array traversal or data redaction. Projected output schemas are descriptive views, not upstream response validators, server-side projection promises or actual returned records. No provider calls.

## Acceptance evidence

| PRD | Evidence and scope |
|---|---|
| FR-01/02, AC-02/08 | Versioned source manifests and actual RDF graph; declared field concepts, aliases, source-local group, unit/source/license/provenance. Historical importer preserves logical schemas and flags seven incomplete type/shape definitions. 166/166 exact field-ID lookup in public DEV inventory. Broad retrieval categories are not numerical equivalence. |
| FR-03/04/06, AC-01/03/06 | Agent-supplied structured requests, exact qualifiers, ambiguity candidate IDs, direct/adjunct paths, per-request counts and budget reporting. Synthetic multi-need and eight-route tests; historical bulk GPa calculated -> 2 routes; literature -> 5 routes; Young modulus -> uncovered. No fixed K or internal query interpreter. |
| FR-05, AC-04 | Input contract unchanged; syntactic JSON Schema validation; nested simple object projection with transitive local defs, escaped reference names and rejection of remote/missing/arbitrary/dynamic references and unsupported ancestors. No general-purpose compatibility claim. |
| FR-07, AC-05 | Separate prepermitted catalogs, no denied source/field/vocabulary leakage in the fixture, no invocation. Host-sanitized scope contract, not a general authorization product. |
| FR-08, AC-07 | Source/alias/annotation update, delete, reload, revision change, invalid replacement atomicity and snapshot consistency tests. |
| FR-09, AC-09/10 | Runnable isolated research modules and example, pinned source/API-only hashes and dependency receipt, complete local test suite. No old-core, model/provider, private asset dependency. Fresh installation and hosted CI not performed. |

FR-10 richer semantics and source-format coverage are conditional. Gate B is scoped to the demonstrated host-permitted research PoC; future production qualification remains outside this gate. The only active capability retrieval backend is RDFLib/SPARQL plus a small schema adapter. It is arm C, not a distinct invented D.

## Reproducibility receipt

Previous session ran all four test modules together on the implementation at 51744aa: Python 3.13.5, 29 unittest methods passed (6 baseline, 7 catalog, 8 historical inventory, 8 discovery contract). Historical field-ID subtests all passed. This session rechecked the committed file identities, test and contract source; it did not rerun the local suite. Test runtime is not an operational latency measurement.

Exact changed Git blobs: ontology_catalog.py f6f99bd17d23f25b62522c7bf6692db2640843f4; test_discovery_contract.py 6842d19bbf44572e8558e3d68288b5c2a58747be; test_historical_inventory.py 80c2ee291cfe10a87cfffd1e5cb93ba61dd412b2. Original public fixture blob fbfe0dcf5b2bfcff325bf673d5bcd3bab5b3985e; only the exact API-array extract da3b3dbda4173fec83d7fee064d01202fa69b04e was transported locally. No gold/query/call labels enter graph construction. See [milestone 2](gate-b-milestone-2.md).

Run in this directory of a repository checkout:

```sh
python -m pip install -r requirements-local-py313.txt
python -m unittest -v ontology_baseline test_ontology_catalog test_historical_inventory test_discovery_contract
```

Previous local execution used SR_API_EXTRACT=/tmp/sr1899/apis.json (pinned API extract) with the same unittest command. The environment file records observed direct and active transitive package versions, not a cross-platform hashed lockfile or evidence of a fresh install. Local GitHub DNS previously failed; publication used GitHub connector and matching tested source blobs. No full legacy repository tests, hosted CI, external model, live provider, independently authored evaluation, token/latency or answer-success measurement.

## Gate C handoff

Freeze a comparable external-agent protocol under #1900 before scoring; use FULL, ordinary tool-level retrieval, and C (this standard RDF implementation). Match metadata and source fixture, expose discovery costs, and distinguish actual wire payload from the schema view. Reuse C as implementation; no fabricated distinct D. Historical schema inventory and exposed 110 queries are DEV only. The choice to stop at a minimal discovery core is deliberate; add no planner/executor/LLM or generic graph engine. No release or merge before #1897 decision.

# Gate B milestone 2 — historical inventory schema-only discovery

Date: 2026-11-27. Issue #1899, PRD FR-01–FR-09 / AC-01–AC-10. Depends on Gate A ADR-001 and Gate B milestone 1. This is a DEV engineering result, not Gate B completion or decision-grade performance evidence.

## Inputs and provenance

The already public historical fixture `tests/fixtures/original_paper_full_replay.json` has pinned Git blob `fbfe0dcf5b2bfcff325bf673d5bcd3bab5b3985e`. [historical_inventory.py](historical_inventory.py) extracts only `inventory.apis`, not archived queries, calls, labels, gold, intent definitions or answers. The exact compact UTF-8 API array is 55,736 bytes, blob `da3b3dbda4173fec83d7fee064d01202fa69b04e`. All 19 APIs, 166 fields and 80 parameters are present. The importer checks the full source blob and API-only blob when run from the repository; it also supports a separately hash-verified API-only transport. No second fixture copy is committed.

This is a historical logical schema manifest, not live OpenAPI/MCP or verified provider wire/API behavior. Each API is represented as its historical logical search endpoint. Dotted names are literal logical field identifiers, not inferred nested JSON paths. Parameter requiredness, field names, source descriptions, literal type, units, identifiers, field groups and declared historical source/license metadata are retained. No output requiredness inferred. Two Materials Project enum domains are not specified and cannot be validated; five other properties have unspecified object shape or datetime format. These seven limits are flagged in property schemas. No invocation-ready contract, live source validation or legal license conclusion is claimed.

## Meaning policy

- 166 source-qualified field concepts are individually discoverable. Local field names and declared aliases remain available except explicit shared alias delegation; collisions across distinct concepts remain ambiguous.
- Five reviewed capability categories: bulk modulus, shear modulus, Young's modulus (no source field), research paper, citation count. They are retrieval categories, not OWL equality, unit conversion or equivalence of measured values. Historical descriptions distinguish VRH (Materials Project) and Voigt (JARVIS). Both are alternatives for the broad bulk/shear category, not identical measurements.
- The historical fixture's 15 declared equivalent_to relations remain in the pinned source. They are not imported as unconditional equality edges or used to infer mappings. Only the explicit reviewed mappings are active in the graph. The new mapping table is a development annotation, not independent task gold.
- Research paper matches title/abstract-like fields on the five literature APIs. Citation count maps only to Crossref is-referenced-by-count; reference-count may appear as group context but is not the same concept. A vague elastic modulus request is ambiguous rather than silently resolved; no Young's modulus source is invented.
- Existing field-group expansion includes related source-local fields and identifiers. Returning a capability does not establish completeness of a scientific answer, exact input arguments or a cross-source join.

## Actual local execution

Python 3.13.5, RDFLib 7.5.0, JSON Schema 4.26.0, pyparsing 3.3.2. The connector fetched the pinned public fixture; only the exact API array was transported into the local environment because git ls-remote failed DNS. Its local Git blob matched the connector-derived blob above. The full fixture file itself was not locally checked out. No fresh installation or hosted CI. The pre-existing ontology_catalog.py was restored locally with Git blob `10b6785c69f432577039817439f7061d765c90d8`, identical to the committed core. No core modifications.

Run in this directory from a repository checkout:

```sh
python -m pip install -r requirements-baseline.txt
python -m unittest -v test_historical_inventory
python historical_inventory.py "bulk modulus" "research paper"
```

Actual local command used the exact API-only transfer:

```sh
SR_API_EXTRACT=/tmp/sr1899/apis.json python -m unittest -v test_historical_inventory
```

Seven new unittest methods passed, including a subtest for each of the 166 source-qualified fields. This does not re-execute the 13 milestone-1/baseline tests; those prior receipts remain separate. New code [d95aa06](https://github.com/JDeun/SchemaRouter/commit/d95aa06246c562be0ed504fac2eb703fd1f28167) was published only after verifying GitHub blob equality with locally tested files: historical_inventory.py `7a771611e8737020514589fc042fb89ec16f2b97`; test_historical_inventory.py `02f6676c3567598dbbe58b7ef86ba2f0e70f8f77`.

Observed graph: 2,227 triples, 171 concepts (166 field-local plus five capabilities). Catalog revision `ae604de5f0ac039fd8fc2ee3d15b3a82a564c47cde1beb75aeeb74bb2e6660e5`. 166/166 qualified identifiers returned their one original logical route and contained the selected field. Tests validated required inputs, metadata/group memberships, syntactic projected JSON Schema, ambiguity/unknown handling, type limits, source pin failure, persist/reload equality and explicit budget omission. No providers or models called.

Example request: external agent supplies two search requirements, bulk modulus and research paper. Both report matched. Seven routes, no fixed K5:

| Route | Full fields | Projected | Selected logical output fields |
|---|---:|---:|---|
| arXiv | 10 | 4 | entry_id, primary_category, summary, title |
| Crossref | 13 | 5 | DOI, abstract, subject, title, type |
| Europe PMC | 7 | 3 | abstract, pmid, title |
| JARVIS | 15 | 4 | bulk_modulus_kv, formula, jid, shear_modulus_gv |
| Materials Project | 22 | 5 | formula_pretty, g_vrh, k_vrh, material_id, poisson_ratio |
| OpenAlex | 7 | 4 | abstract, doi, id, title |
| PubMed | 6 | 3 | abstract, pmid, title |
| Total | 80 | 28 | 65% fewer output field names vs the same selected full schemas |

The 65% is one selected-set field-count comparison, not schema byte/token savings or answer quality; input schemas are unchanged and projected field groups include related fields. The 166/166 result is registered field-ID lookup integrity, not semantic generalization or required-field recall on independent tasks. No comparison with external-agent baseline A/B, no latency benchmark, no deployment claims.

## Remaining contract work

FR-01/02/03/04/05/06: historical normalization and exact schema-only discovery demonstrated; need precise structured per-requirement constraints, traceable per-view match versus adjunct fields, complete coverage semantics and handling of budgets. FR-05/07: adversarial schema/ref closure, projection/declaration consistency and host-permitted schema/metadata isolation must be reviewed; no dynamic authorization assumed. FR-08: annotation lifecycle and consistency edge cases. FR-09/AC-10: dependency/environment reproducibility and complete isolated suite. FR-10 general format ingestion/multilingual meaning expansion is conditional. The historical importer is not a general adapter or a new engine.

Keep #1899 open. Next priority: audit retrieval/projection contract, then add focused tests for qualifiers, explicit hit paths and permitted-surface behavior; do not expand to Planner, Executor, custom graph engine or agent. #1900 owns matched-agent evaluation. If equivalent to generic ontology baseline C, no fabricated D arm. Main, historical paper branch and existing releases unchanged.

# Gate B milestone 1 — versioned RDF catalog and discovery views

Date 2026-11-27. Issue #1899. PRD FR-01–FR-09 / AC-01–AC-10. This is an engineering checkpoint, not Gate B completion.

## Vocabulary decision

W3C [WoT Thing Description 1.1](https://www.w3.org/TR/wot-thing-description11/) §§5.3.1–5.3.2 and 6.3.10 already describe interaction affordances with input/output DataSchema, units and semantic annotations. [WoT Discovery](https://www.w3.org/TR/wot-discovery/) §7.3.2.3.3 defines optional SPARQL directory search. This is directly overlapping prior art; no novelty claim for semantic tool directories. Use standard RDF/SPARQL and SKOS concept/alias vocabulary, not a bespoke graph engine. The WoT mapping is conceptual: tools/endpoints correspond roughly to Things/action affordances; inputs/outputs to DataSchema. The PoC intentionally does not claim WoT TD compliance or import an external ontology at runtime. WoT DataSchema is a subset of JSON Schema; preserve original JSON Schema 2020-12 contracts as literals and avoid lossy conversion to TD. Keep only the small local predicates necessary to link source-qualified routes, parameters, response paths, concept mappings, groups, metadata and revision. No external schema fetches, OWL reasoning or provider access. No upstream code copied.

## Implemented and exercised

- [ontology_catalog.py](ontology_catalog.py): RDFLib Graph, fixed prepared SPARQL query with bound concept identifier, reviewed aliases, source/tool/endpoint compound identity, typed source manifests, field annotations, source and catalog revision digest. Semantic lookup operates on the actual graph, not a tool-description ranker.
- Catalog.put/remove rebuild a detached graph and replace only after validation. Turtle save with same-directory temporary file and replace; reload rebuilds from manifest and compares triples. This detects inconsistent snapshot contents, not malicious replacement of the entire consistent graph or concurrent writer safety.
- Catalog.discover takes external-agent-owned search labels/concept IDs and an optional caller route budget; returns route IDs, full original input schema, selected output schema view, declared field metadata, per-term match/ambiguity/uncovered/budget/projection status and omitted route count. No LLM, intent registry, execution order or argument values.
- Projection of explicit property paths through simple object ancestors; identifiers and one-hop declared source-local field group expansion; selected subtrees preserved; necessary local root $defs closure included, unused root definitions omitted. Reject unsupported projection ancestors rather than silently dropping constraints. Copy original input schema (not an input-minimization claim). No remote references or dynamic reference scopes accepted by the supported subset.
- Host supplies the already-permitted catalog including concept labels. No dynamic field-level authorization or execution authority. Never expose the trusted snapshot/store directly to untrusted clients. No claim that a schema view changes provider wire payload or that projected schemas validate unprojected provider records.

## Reproduce

From this directory, install the already-pinned requirements-baseline.txt into an appropriate clean environment, then run:

```sh
python ontology_baseline.py -v
python -m unittest -v test_ontology_catalog
```

Observed in existing local Python 3.13.5 environment (RDFLib 7.5.0, jsonschema 4.26.0, pyparsing 3.3.2): baseline 6/6 and milestone 7/7 passed. Exact source blobs verified with Git hash-object and GitHub create_blob before publishing code [0a882aa](https://github.com/JDeun/SchemaRouter/commit/0a882aa3f922dad6995d653c5dbc1e9beddfc109): ontology_catalog.py 10b6785c69f432577039817439f7061d765c90d8; test_ontology_catalog.py e0d8d0a669fe38a261a7657c857f8b1a45bce416. No fresh dependency install, clean hosted CI, or full historical repository tests. Local git ls-remote failed DNS; source and tests were published via the GitHub connector with matching blobs.

### Agent discovery example (synthetic)

```python
from ontology_catalog import Catalog
from test_ontology_catalog import CONCEPTS, sample, literature

catalog = Catalog(CONCEPTS, [sample(), sample("alternative", "bulk_modulus"), literature()])
result = catalog.discover(["bulk modulus", "research paper"])
```

Actually observed: 71 triples, three matching route views, both concepts matched. Alternative route fields: id + bulk_modulus.value; materials route: id + k.value; literature route: doi + title + abstract. Required query/topic input contracts retained. No actual material values or papers retrieved. Elastic modulus alias intentionally ambiguous; no invented physical equivalence. The graph does not interpret an end-user query. A matched term means at least one relevant projected field, not complete scientific answer or proof of all members of a composite concept.

## Requirement traceability and limits

| PRD | Milestone evidence / remaining |
|---|---|
| FR-01/02, AC-02/08 | Source-qualified typed manifests and declared aliases/metadata/groups implemented on synthetic fixtures. Full source contract validation, provenance review, source-format import, qualifiers and composite concepts remain. |
| FR-03/04/06, AC-01/03/06 | Bound SPARQL, three synthetic matches, ambiguous/uncovered, 8-route and explicit budget tests. Per-route requirement provenance, structured qualifier filters and full coverage reporting remain. |
| FR-05, AC-04 | Restricted nested object and transitive local refs test; complete input preserved. General JSON Schema semantics, nested IDs/dialects, conditional/discriminator/array paths and reference-scope edge cases need explicit adversarial review. Unsupported ancestors rejected; not general-purpose projection. |
| FR-07, AC-05 | Prepermitted single catalog smoke only; fine-grained permission isolation and schema/metadata disclosure review remain. |
| FR-08, AC-07 | Persist/reload, revision change, stale field removal, invalid put atomicity, inconsistent snapshot rejection. Annotation changes and concurrent/durable storage not qualified. Full graph rebuild per change: measure before optimizing. |
| FR-09, AC-09/10 | Seven local synthetic tests and example; actual public historical inventory import (19 tools/166 fields), clean environment lock/checks and documented adapter contract remain. |

Next: freeze the normalized public contract, validate annotations/visibility and schema-reference edge cases; map and run the exposed 19-source historical inventory without importing legacy planner/executor or archived answer labels. Add reproducible tests and review before closing #1899. Same-agent/held-out results remain #1900. If this is merely baseline C with validation, retain C as the actual arm, no invented distinct D. Main and old paper branch unchanged; no release.

# Gate C1 — conditional schema exposure DEV results

Status: **FAIL** for the frozen first-pass retrieval hypothesis; project-level decision remains **INCONCLUSIVE** (no independent agent evaluation). No release or promotion.

## Protocol and provenance

- Preregistered protocol and harness: [892b84c](https://github.com/JDeun/SchemaRouter/commit/892b84c462e0f3c6a405c38289b4b7f2676f6ea0); [protocol](gate-c1-dev-protocol.md), [runner](dev_benchmark.py). Frozen discovery core: 51744aa.
- Public historical inventory blob fbfe0dcf5b2bfcff325bf673d5bcd3bab5b3985e; exact API extract blob da3b3dbda4173fec83d7fee064d01202fa69b04e; case extract blob 5b3f89358fe2bdaee8011bbb62786039e0ae19c1. Both extracts and frozen core locally hash verified; full fixture not locally checked out due to DNS. The archived selected calls are **references, not independently adjudicated gold**. The experiment supplies archived concept strings, not full natural-language user requests, source/intent cues, or new agent outputs.
- Actual local run: Python 3.13.5, RDFLib 7.5.0, jsonschema 4.26.0, pyparsing 3.3.2; Linux x86_64. Command: `python dev_benchmark.py --api-extract apis.json --case-extract cases.json --out run1`. No provider/model calls. Local model weights/inference endpoint unavailable and DNS blocked external downloads. No fresh dependency installation.
- 110 cases × 5 arms = 550 rows; three deterministic repetitions per case/arm; times below are medians per case, then p50/p95 across positive cases. Exact raw rows.jsonl SHA-256: 016aff71abdada94833acff356d80fc513c9b16a7a9bae6b1e38fea1b365d134. See [summary](gate-c1-dev-summary.json). 
- All arms share the normalized inventory, with 19 permitted routes, 166 annotated output fields and 2,227 RDF triples. BM25 uses the same field annotations and concept aliases as RDF, k1=1.2 and b=0.75, positive scores only, no learned ranker. RDF is the actual frozen Catalog.discover implementation, not an emulated variant. No extra D arm.
- 102 positive reference cases, 110 reference tool occurrences and 868 field occurrences. All reference pairs exist in FULL. Eight no-reference cases have empty terms; B/C return empty and A exposes all by construction. These are not meaningful independent no-fit classification examples.

## Results on the 102 positive reference cases

| Arm | Tool recall (micro) | Field recall (micro) | Complete reference sets | Empty | Mean exposed tools | Mean exposed fields | Mean envelope + request bytes | p95 local ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 100.00% | 100.00% | 102 | 0 | 19.00 | 166.00 | 83,257 | 0.856 |
| BM25-5 | 93.64% | 93.55% | 95 | 1 | 3.52 | 46.72 | 23,494 | 0.339 |
| RDF-5 | 21.82% | 20.05% | 7 | 72 | 0.32 | 2.28 | 2,577 | 2.625 |
| BM25-all | 99.09% | 99.08% | 101 | 1 | 5.45 | 61.95 | 31,098 | 0.763 |
| RDF-all | 21.82% | 20.05% | 7 | 72 | 0.32 | 2.28 | 2,580 | 2.833 |

Bytes are UTF-8 JSON serialization of actual result envelopes including metadata, plus discovery request for B/C; not model token counts or provider response traffic. Schema-only mean bytes are in summary. FULL is an exposure ceiling, not evidence that a model would select correctly. B5 reduces bytes by 71.78%; RDF5 by 96.90% but mostly by missing references. No efficiency win at matched coverage. One-shot build: RDF 83.17 ms; BM25 5.68 ms, excluding shared normalization. Not a throughput/scale or memory benchmark.

### Diagnostic: archived field hits by category (B5 vs C5)

| Category | n | Reference field occurrences | BM25-5 hits | RDF-5 hits | RDF empty |
|---|---:|---:|---:|---:|---:|
| ambiguous_query | 6 | 25 | 25 | 0 | 6 |
| chemical_lookup | 12 | 156 | 156 | 99 | 0 |
| cross_source_comparison | 8 | 176 | 176 | 0 | 8 |
| literature_search | 10 | 80 | 72 | 0 | 10 |
| multi_field_property_lookup | 10 | 117 | 117 | 46 | 3 |
| provenance_sensitive_query | 12 | 78 | 30 | 0 | 6 |
| single_tool_property_lookup | 36 | 192 | 192 | 0 | 36 |
| unit_sensitive_query | 8 | 44 | 44 | 29 | 3 |

On these exposed cases RDF-all receipts across 216 input terms: 48 matched, 115 ambiguous, 53 uncovered. In particular band_gap, formation_energy, energy_above_hull, density, title, summary, abstract, authors and stability are ambiguous. The importer creates many source-local field concepts and only five reviewed shared concepts. Same generic property aliases across sources collide with concept IDs, even when those sources might be reasonable alternative providers of a category. Distinguish these from real scientific ambiguity (different elastic moduli, calculation methods and source conditions). Some exact spelling variants are missing (elastic_modulus vs elastic modulus); some terms are scientific topics or missing capabilities, not schema fields. No evidence that K is responsible: unlimited results are identical in recall. No tuning on these exposed outcomes in this run.

## Decision

- Frozen first-pass implementation fails the prespecified engineering recall threshold (95%). It should not be promoted. Even the ordinary BM25 baseline is much stronger on this conditional diagnostic.
- Do not infer that RDF itself is ineffective, that task accuracy is 20%, or that a real agent cannot reformulate/disambiguate a request. The experiment omits fresh agent interpretation and independent tasks.
- Before expanding implementation, consider a narrowly scoped prospective ontology revision: source-grounded capability categories for alternative providers, distinct method/provenance, alias spelling normalization and explicit candidate discovery for genuine ambiguities. Review against source schemas without using archived selected calls as annotation targets. No internal LLM/planner/executor. Predeclare any changed method and freeze before a new evaluation. If the generic RDF baseline remains equivalent, no distinct algorithmic D; the only justified product could be a thin adapter.
- Gate C2: same external agent/model, frozen independently authored tasks and authorized fixture, paired final task success and full operational token/latency costs, noninferiority and precision per #1900. No model available locally; independent set not obtained. Keep #1900 and #1897 open. No new release, legacy merge or GO decision.

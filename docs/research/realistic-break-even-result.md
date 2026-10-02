# Realistic routing break-even result

This document records the frozen synthetic break-even matrix introduced by #693 after the retrieval hot-path optimizations in #696. It is a routing benchmark, not evidence of production adoption or final-answer quality.

## Question

The benchmark asks whether SchemaRouter's typed capability retrieval is justified by raw catalog size, or by the ambiguity and schema heterogeneity of the catalog.

The frozen matrix covers catalog sizes **20 / 50 / 100 / 250 / 500** and **low / medium / high** ambiguity. It compares a strong schema-aware lexical baseline, SchemaRouter exhaustive/full retrieval, and SchemaRouter auto/indexed retrieval.

## Routing quality

SchemaRouter auto matched the exhaustive/full candidate selection in every matrix cell:

- auto/full selection mismatches: **0**
- required-tool recall: **1.0**
- unsupported rejection: **1.0**
- false-route rate: **0.0**

For the strong schema-aware lexical baseline:

| Ambiguity | 20 | 50 | 100 | 250 | 500 | Unsupported rejection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| high | 0.583 | 0.667 | 0.583 | 0.583 | 0.583 | 1.000 |

The low/medium fixtures therefore do **not** establish an accuracy advantage for SchemaRouter. The high-ambiguity fixtures do: the lexical baseline loses required-tool recall while SchemaRouter retains the frozen routing-quality metrics above.

## SchemaRouter auto latency

| Catalog size | Low p50 / p95 (ms) | Medium p50 / p95 (ms) | High p50 / p95 (ms) |
| ---: | ---: | ---: | ---: |
| 20 | 0.305 / 0.348 | 0.546 / 0.608 | 0.680 / 1.105 |
| 50 | 0.446 / 0.752 | 0.951 / 1.315 | 0.792 / 2.406 |
| 100 | 0.657 / 0.964 | 1.574 / 2.162 | 0.927 / 4.585 |
| 250 | 1.304 / 1.672 | 3.536 / 4.738 | 1.424 / 11.443 |
| 500 | 2.318 / 2.685 | 6.890 / 8.471 | 2.245 / 24.053 |

The high-ambiguity tail is not free: p95 reaches about **11.44 ms** at 250 tools and **24.05 ms** at 500 tools.

## Break-even interpretation

The frozen classification is:

- **low / medium ambiguity:** simple routing sufficient on this fixture;
- **high ambiguity, 20 / 50 tools:** typed-routing benefit with low overhead;
- **high ambiguity, 100 / 250 / 500 tools:** typed-routing benefit with measurable overhead.

The result changes the product framing. **Catalog size alone is not the useful break-even axis.** SchemaRouter is better motivated by heterogeneous providers/protocols, overlapping sibling operations, field semantics, datatype/unit/qualifier requirements, unsupported-request rejection, and policy-sensitive execution boundaries.

A large but lexically obvious catalog may not justify SchemaRouter. A smaller catalog with difficult semantic/schema distinctions may.

## Provenance

Canonical corrected 20-iteration workflow run: `37017834707`.

Artifact:
- name: `realistic-break-even`
- id: `11231726626`
- digest: `sha256:2a7323b1ab6c23519f139901e74bd49d999cb152f65a96a2213ac2f643f522ad`
- benchmark head: `4b26027601cf7ebedbc69fd46fc3fbedb9acf30e`
- benchmark implementation: `scripts/benchmark_realistic_break_even.py`
- workflow: `.github/workflows/realistic-break-even.yml`

An earlier exploratory matrix encoded unsupported fields only as free-form concepts. It is **not evidence** and is superseded by this corrected run, which uses semantic IDs plus active field-evidence requirements and fail-closed unsupported requests.

## Claim boundary

This is a deterministic synthetic retrieval benchmark. It establishes a controlled routing break-even result only. It does not establish production adoption, independent reproduction, real-world workload prevalence, or end-to-end agent-answer quality.

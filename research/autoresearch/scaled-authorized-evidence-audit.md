# #1428 — Pinned scaled authorized DEV evidence audit

Source: [successful Actions run #38839753512](https://github.com/JDeun/SchemaRouter/actions/runs/38839753512), artifact ID 12020808680, `scaled-authorized-dev-38839753512`. The raw 81-case 567-call `report.json` SHA-256 is `a076df488754229f8090db5f9fdf69310f21ccad018af4fe1dee22afe6f496c0`; all source/corpus hashes and exact workflow-run metadata are frozen in `benchmarks/scaled-authorized-dev-frozen-source.json`.

## Observed negative transfer (reviewed archive)

| Condition | Required routes / 63 | Output fields / 90 | Unsupported nonempty / 18 | Unauthorized | measured total p95 ms |
|---|---:|---:|---:|---:|---:|
| final V1 K24 | 39 | 48 | 18 | 0 | 2308.13460 |
| V2-weighted K24 | 39 | 48 | 18 | 0 | 2322.51186 |
| V2-weighted K32 | 39 | 48 | 18 | 0 | 2388.34154 |
| V2-weighted K40 | 39 | 48 | 18 | 0 | 2480.40016 |
| V2-weighted K48 | 39 | 48 | 18 | 0 | 2561.61302 |
| V2-weighted K56 | 39 | 48 | 18 | 0 | 2629.47668 |
| V2-weighted K64 | 39 | 48 | 18 | 0 | 2716.16785 |

The exposed synthetic test contains **7 supported and 2 unsupported local scenarios per language**, repeated on all three catalog sizes (81 total cases). Supported English required-route recall is 21/21, Korean 9/21, and Japanese 9/21; every wider pool retains identical hit counts. English metadata and closely named synthetic distractors constrain this outcome; avoid any commercial or independently blinded conclusion. The measured ~2.3s–2.7s p95 is the **actual synchronous authorized retrieval plus rerank path on this synthetic fixture**, not the historical isolated planner-only millisecond study, nor a real-agent latency measurement.

**Do not promote the K56 candidate:** this DEV result shows no route/field gain, no no-fit reduction, and higher CPU time. The measured historical 150ms CPU research threshold is not met by any variant on this workload. A nonempty shortlist for an unsupported query is *not* proof of a physical unsupported action. Zero unauthorized candidates on a local synthetic role fixture is *not* proof of production authorization safety.

## Independent evidence validation

`scripts/research_scaled_authorized_report_audit.py` downloads no model and executes no capabilities. It rejects tampered or incomplete 81-case source reports by checking:

- Exact archived raw and canonical JSON SHA, source commit, task fingerprint, expected 567 calls, 100/250/500 scales, six registered widths and provenance.
- 27 identical case identities per size, no missing/duplicate case, exact language/role strata and complete condition matrix.
- No invented supported route or output-field matches, no duplicate or overwide shortlists, no unauthorized candidate counters, no false independent/promotion/release claims.
- Independently recomputed required-route/field, no-fit, per-case field-coverage, group aggregate, p95 and schema-byte values; negative and regressions are **retained**, not hidden.
- Per-language/role/size regression plus research CPU guard and positive measured gain. These constitute a retrospective **DEV diagnostic** only; every output has `may_promote=false` regardless.

Run from the checkout with:

    python -m pytest -q tests/test_research_scaled_authorized_report_audit.py
    python -m scripts.research_scaled_authorized_report_audit --input report.json --manifest benchmarks/scaled-authorized-dev-frozen-source.json --output audit.json

The read-only GitHub Actions CPU workflow re-downloads exact successful experiment run #38839753512, checks raw SHA, audits it and archives both JSON artifacts. It does not start another 567-call experiment. No OAuth secrets, paid API, GPU, external coding agent, production edits or release token.

## Outstanding requirements

Real independent provider schemas, new human-reviewed query/field labels without source/template overlap, authenticated principal evidence and fixed-agent end-to-end task success remain unmeasured (#1346/#1412). The historical frozen #432 negative evaluation and held v0.18 release #1356 do not change.

# Source-locked real CPU E5 against opt-in fixed-K semantic diagnostic (DEV)

**Preregistered engineering comparison before new score run:** This study reuses
already-exposed, author-written development queries from `scripts/research_open_meteo_real_openapi_dev.py`
and genuine original publisher-authored Open-Meteo YAML from exact
`open-meteo/open-meteo` revision
`b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4`, nine source groups:
air-quality, climate, elevation, ensemble, flood, forecast,
historical-weather, marine, seasonal. All nine original upstream Git blob
hashes, paths and sha256 bytes must validate against
`benchmarks/open-meteo-openapi-real-source-dev-manifest.json` before any
model inference. No authenticated Open-Meteo service or tool is invoked.

This is explicitly **same-author, already-consumed developer data**, not a
new independent evaluation. The 27 supported English/Korean/Japanese requests
(9 per language, each with its one original publisher source-group route)
and 9 unsupported (three unsupported intents per language) are pre-existing.
Do not change prompts, gold or supported/OOD labels to improve a result.

## Frozen question and treatments

Does the just-implemented [#1474 opt-in source-verified read-only diagnostic](https://github.com/JDeun/SchemaRouter/pull/1474)
run a **real CPU** `intfloat/multilingual-e5-small` at exact Hugging Face
revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, and what is its
**unmodified** strict K=5 native tool-group recall vs the same public
source-restricted lexical `retrieve_authorized(query, k=5)` on 36 original
queries? No reranker promotion or production default changes. The comparison
must use **the same source registry, principal and five-route budget** for
both arms. Do not add a lexical+model union or variable-width recall
augmentation; no threshold/no-fit calibration is performed. If the backend
returns fewer than K, preserve that failure separately; never backfill from
oracle gold.

## Hard guards and metrics

- Both arms bound to the exact authorized nine original OpenAPI publisher
  route IDs. No unregistered IDs, no unauthorized namespace, no callable
  executable result, and no external network except fetching pinned public
  source/model dependencies.
- Model option text comes only from current principal-visible, already
  registered `CapabilityCandidate` descriptions and visible fields. The
  research method has a physical catalog cap of nine and a strict serialized
  model **input cap 128 KiB**; returned native shortlist max **5**.
- Pinned CPU model loads via `SentenceTransformer(... revision=SHA,
  trust_remote_code=False, device="cpu")` with actual
  `E5CachedEmbedder` + `EmbeddingDecisionBackend`. Report per-row true
  CPU inference/retrieval wall times, summary median/nearest-rank p95
  diagnostic times, model context bytes and peak RSS, local Actions CPU info,
  original upstream provider source file digest, model source identity.
- Supported (n=27) report paired strict Top1 and K5 **native required
  source-route-group hit** for lexical vs semantic per EN/KO/JA and aggregate.
  This metric is not native required **input-field recall**, fit calibration,
  production-route execution or final-agent answer success.
- Unsupported (n=9) report **nonempty shortlists** (false no-fit evidence
  exposure) for both arms; no threshold learned. Abstentions, partial-K,
  K-sized choices and failures must not be silently interpreted as safe
  refusals. Preserve row-level raw outcome including native selected IDs.
- Gate is **valid reproducible DEV evidence**, not improving any observed
  score: negative model results are accepted and published; throw on source
  drift, width/authority breach, incomplete cases, missing real-model source,
  invalid metric denominator, NaNs or contradictory roles.

## Evidence boundaries

- No new independently written source-native prompts; EN/KO/JA labels are
  identical to prior DEV uses. The previous genuine provider E5 scoring
  already informed future question selection and this integration test; it
  therefore has **no external validity for commercial claims**.
- Unlike lexical-only defaults, this opt-in diagnostic does not train or
  validate a reliable unsupported/no-fit detector. Nine unsupported requests
  are important **negative** evidence, not successful refusals.
- GitHub Actions `ubuntu-24.04` local CPU timings are not stable production
  service p95/SLA; first-run model load/downloading is excluded from per-query
  inference p95 and separately reported by logs. Schema/token output budget
  must be evaluated separately from serialized model-input bytes.
- No explicit multi-step agent execution, browser, live permissions
  authentication, real Open-Meteo API requests, independent native
  publisher review or separate held-out tasks. Historical frozen #432
  negative multilingual agent success and ServiceNow strict-K5 E5 failure
  stay unchanged, regardless of new DEV results.

No change to `src/schemarouter`, product decision defaults, host release
gates or v0.18 PR #1356. Subsequent product claims require entirely new
publisher/author-independent disjoint EN/KO/JA/OOD case authorship, fixed
schema/token and CPU budgets, paired actual agent success, audited source
permissions, calibrated false accepts, and prospective preregistration.

# #1346 — Nine authentic Open-Meteo provider OpenAPI contracts (CPU DEV, zero tool calls)

## Source, provenance and attribution

The actual [Open-Meteo provider-maintained OpenAPI repository](https://github.com/open-meteo/open-meteo/tree/b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4/openapi) contains nine OpenAPI 3.1 files for **air quality, climate, elevation, ensemble forecasts, flood, conventional weather forecast, historical weather, marine forecasts and seasonal forecasts**. These documents are **provider-authored**, unlike previous synthetic JSON descriptions. Original provider materials are marked [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and attributed to Open-Meteo. This study is not affiliated with or endorsed by Open-Meteo.

Manifest `benchmarks/open-meteo-openapi-real-source-dev-manifest.json` pins the provider repository, exact Git commit `b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4`, all nine source paths and **each Git blob SHA-1**. The Linux Actions runner downloads exactly these public *documentation* files, verifies Git object identity and archives additional raw SHA-256 for each. It does NOT call live Open-Meteo endpoints, use API credentials or run any returned capability.

## Experiment

`scripts/research_open_meteo_real_openapi_dev.py` runs the **current** `tool_from_openapi` against each genuine YAML document, preserving parsing errors and unsupported features as explicit source-specific negative evidence. It registers the successful parsed read-only GET capabilities in `InMemoryRegistry`, applies a synthetic Viewer role under explicit allow and default deny, then runs real `SchemaRouter.retrieve_authorized(PlanRequest, principal, k=9)` with **27 author-written English/Korean/Japanese supported queries** (one query per provider source per language), plus **9 unsupported delete/transfer/purchase prompts**.

Measured report: actual published source bytes and SHA, parser coverage/failures, currently registered operation identities, source-level Top1/Top5 of supported prompts, unsupported **nonempty retrieval** (retrieval is always an unthresholded shortlist, NOT an execution or semantic acceptance verdict), per-request query time, peak process RSS, exact repository commit. No actual action is invoked. **If a spec does not parse, its attempted path remains logged and no result is inferred for it.**

### Score-zero and registry-order caveat

The current lexical ranker may return a full shortlist of 9 tools even when
no lexical match exists. Such deterministic **zero-score fallback order** is
not evidence of Korean/Japanese semantic understanding. The report therefore
includes each Top-1/Top-5 score, exact Top-1 tie count, selection source,
`all_nonpositive` flag, and per-language nonpositive case counts. Do not
interpret coincidental matching at fixed catalog order as real route recall;
both ordinary Top-K identity and evidence of positive scoring must be
reported. Unsupported nonempty Top-K likewise does not equal tool dispatch.

## Honest limitations

- Authentic publisher-authored **schema source**, but only **one external provider** and nine small endpoint families. It is neither 100/250/500 truly distinct providers nor cross-source-disjoint test labels.
- All supported and unsupported prompts are self-authored development data; no independent user-intent annotation or calibrated no-fit threshold.
- The policy principal is a programmatically supplied synthetic Viewer, **not** an authenticated host identity.
- This study does not call a real service, run an agent, evaluate arguments against live schema semantics, or qualify provider-side tool execution.
- No embedded model inference: this is the current product lexical typed retrieval, not a test of MiniLM/E5. A Korean/Japanese zero-hit is a useful *source-specific DEV* negative, not an externally confirmed product failure rate.
- The report never authorizes product changes, remote actions, benchmarks over 500 actual provider schemas, or v0.18.0 release.

**Next required work:** add *separate* independent task annotations and other original provider-maintained API catalogs, user-operation/no-fit verification and fixed-agent, no-call negative testing; keep original frozen #432 result intact. **#1339/#1346 open, #1356 release HOLD.**

Workflow `.github/workflows/research-open-meteo-real-openapi-dev.yml` uses Ubuntu CPU, source checkout and downloaded public docs only, 20-minute bounded run; its untrusted model-risk boundary remains unchanged.

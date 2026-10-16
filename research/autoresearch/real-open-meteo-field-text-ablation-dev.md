# #1339 — Publisher parameter description text ablation on real authorized E5 CPU DEV

## Source-proven fact and narrow new question

Source-attested [#1441](https://github.com/JDeun/SchemaRouter/pull/1441) produced **23/27 Top1, 26/27 Top5** with actual pinned `intfloat/multilingual-e5-small` CPU embeddings over nine genuine Open-Meteo OpenAPI 3.1 documents (all original provider Git blob identities frozen by #1440). EN 8/9, KO 7/9, JA 8/9. Four *supported* misroutes remain, mostly confusion between ordinary weather, marine, flood, ensemble and historical weather. Default current product retrieval remains lexical.

**New diagnostic question:** does adding **the existing authorized request parameter names/param descriptions and declared output field names**, already present in `CapabilityCandidate`, help E5 disambiguate these neighboring provider endpoint contracts? No manually labeled intent, query translation, endpoint operation oracle, gold-route feature or model training may enter candidate text.

## Protocol, predeclared *before CPU results*

Use *identical* nine original Open-Meteo provider-published schemas pinned to `open-meteo/open-meteo@b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4` and exact source hash manifest; same 27 author-written EN/KO/JA supported and nine unsupported questions. Same original `intfloat/multilingual-e5-small` source-pinned checkpoint `fd1525a9fd15316a2d503bf26ab031a61d056e98`; local CPU-only `SentenceTransformer` with `trust_remote_code=False`, existing `E5CachedEmbedder` and `EmbeddingDecisionBackend`.

For every query, FIRST compute the actual public `SchemaRouter.retrieve_authorized(PlanRequest, simulated Viewer, k=9)`; **never** access raw unapproved tool/schema content to enrich E5. Three fixed option passage representations:

1. **original:** exactly the #1441 format of authorized tool description + endpoint description, unchanged.
2. **parameter_names:** baseline plus source-adapter-exposed approved parameter names and declared output fields.
3. **parameter_descriptions:** baseline plus approved parameter names/descriptions and output field names.

Each vector decision receives exactly the same nine *authorized* route IDs. Reject if any added/denied ID, partial ranking, duplicate, invalid score, source SHA mismatch, non-pinned model revision or interrupted CPU study. Record all 36 × 3 ranked complete lists, exact hashes of source and research code, per-language Top1/Top5 supported-source matching, negatives' unthresholded shortlist, timings, and peak RSS.

**Predecision gate:** improving aggregate Top1 alone is insufficient. Candidate variant must not regress English Top1 or Top5 relative to **original** on the same held-out comparison rows, must not lower KO/JA Top5, and must specifically make at least one prior forecast/marine confusion better to be worth *further independent evaluation*. This is a screening criterion on already exposed author-written DEV cases, not a production promotion gate. Even success cannot authorize default model or changed routing, because independent-query/provider and end-to-end evidence are missing.

## Explicit limitations

- Only ONE genuinely independent *schema publisher* with nine read-only endpoints; question authors, query paraphrases and gold labels are not independent.
- The operation and intent labels of real user traffic are NOT provided by a trusted host. Parameter matches can be ambiguously broad (latitude, longitude, hourly, daily); more text might make embedding behavior worse.
- Does NOT test real field value generation, negative no-fit calibration, data-scope projection diversity, authenticated identity, actual Open-Meteo requests, agents or task success. Unsupported prompts still get a nine-route shortlist, but no API call; do not score those as false tool executions.
- We do not tune weights/thresholds or train/select new defaults on this data. Original #432 frozen independent KO/JA negative remains unchanged. Release #1356 HOLD, quality #1339, independent validation #1346 OPEN.

This experiment is read-only Ubuntu Actions CPU with an explicit 40-minute cap and full immutable source/rank report. No paid models, remote agents, live provider execution or GPU.

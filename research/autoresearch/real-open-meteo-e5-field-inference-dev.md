# Source-only multilingual required-field inference (E5 CPU DEV; #1339 / #1346)

## Transition away from an oracle, not a deployment claim

Prior real-provider studies [#1441](https://github.com/JDeun/SchemaRouter/pull/1441), [#1443](https://github.com/JDeun/SchemaRouter/pull/1443) and [#1445](https://github.com/JDeun/SchemaRouter/pull/1445) established: original E5 reranking improved same-author nine Open-Meteo schemas' Top-1 source matching from lexical **7/27 to 23/27**; a human oracle's single exact variable could safely choose **9/27**; the two-variable marine conjunction chose **12/27** and abstained on **15/27**, with no wrong unique selected among this tiny DEV set. **These selected counts use manually supplied operations/variables, so they are NOT the production ability to infer requirements.**

This PR directly measures *one actual attempted inferred component*: local, pinned multilingual E5 mapping a user request to the provider's **already authorized source-defined query enum variables**, **without passing any human gold/operation label to the prediction**.

## Source identity and exact protocol

- Same nine genuine [Open-Meteo publisher OpenAPI documents](https://github.com/open-meteo/open-meteo/tree/b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4/openapi), individually checked against pinned Git object hashes and archived with exact raw SHA-256. The research does not call their live services.
- Pinned genuine `intfloat/multilingual-e5-small` source revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, CPU-only `SentenceTransformer(trust_remote_code=False)`, official SchemaRouter `E5CachedEmbedder` and `EmbeddingDecisionBackend`.
- For **each of the same 36 previously exposed source-authored DEV queries**, first call actual `SchemaRouter.retrieve_authorized(query, principal=simulated Viewer, k=9)`, verify **exact nine allowed GET route IDs**, then extract all bounded `(query_parameter_name, schema_enum_value)` pairs **only from the resulting `CapabilityCandidate.parameters[].json_schema`**. Denied/non-query or nonread-only metadata is excluded.
- Two fixed, publisher-derived no-oracle candidate representations: **enum name only** (snake_case separated into words), or **enum name + original parameter context**. No manual multilingual glossary, special-case route name, reference to correct tool, human gold label, query family or previously calculated oracle ranking is used to build or score a candidate.
- Embed actual user text against these source-authored candidates, record the literal top ten **enum identities and owning currently authorized route IDs**, model/repository/publisher source hashes, CPU latency and peak memory. Use bounded 2,048 unique fields, 1,024 enum values per parameter, zero unsafe mutation.
- **Only after all E5 predicted ranks are fixed**, import the old author-written field requirements from #1445 **for offline diagnostic scoring alone**. Report `field_hit_at_1`, `field_hit_at_5` (any requested pair), and `all_required_hit_at_10` (all requested pairs) stratified EN/KO/JA. Support 27; field gold exists for 24 (3 elevation cases have no enum requirement); unsupported 9 get predictions but **no** claimed correct label/no-fit FPR.
- Fail on source SHA drift, missing or duplicated route IDs, malformed enums, unknown output IDs, source inventory changing with query, absent model checkpoint, incomplete 36-case report, or model inference errors. An original authorized enum declaration is **not** itself proof of user intent or a service authorization.

## Precommitted interpretation

A high field Top-5 score would warrant follow-up experiments to combine *inferred* multiple requirements with an independently established operation/domain contract on **new unseen tasks**. A low score would rule out using raw E5 field name retrieval as an adequate extractor, without adapting fields to this observed corpus. **No threshold or confidence is calibrated here.** A predicted field is *not a trusted host requirement*; it must NEVER directly trigger a tool call. No product default/model selector changes, no registry bypass and no release.

This uses one real external provider's nine original GET schemas but **still researcher-authored exposed queries and gold**, a simulated Viewer, no authenticated principals, no real agents, no unsupported-action classifier or final task success. Historical #432 independent negative remains unchanged; **#1339/#1346 OPEN and v0.18 #1356 HOLD**.

## What commercial qualification still requires

Before commercial claims, this module would need: new query-author-disjoint requests, real multi-provider disjoint source catalogs, independently reviewed operation/domain/field labels; realistic no-fit/unsupported negatives and false-refusal; verified host-supplied principal identity and data scope, explicit **deny/no-call** proofs, agent end-to-end correctness including argument/response fields, CPU p95/p99 at 100/250/500, and repeated boot/wheel/environment compatibility. These are not implemented or inferred by this study.

Original publisher schema source attribution: Open-Meteo (CC BY 4.0); no provider endorsement.

# #1339 / #1346 — Real E5 vs lexical, over only authorized *real publisher* schemas

## Why this is a different test

The [Open-Meteo source audit #1440](https://github.com/JDeun/SchemaRouter/pull/1440) downloads and pins **nine genuine original Open-Meteo OpenAPI 3.1 YAML files** from provider repository Git commit `b0ff3ebbbafa890000ab8bc5f9598a2e4ef64dc4`, verifies each Git blob SHA-1 and successfully exercises the **current actual** `tool_from_openapi` and `SchemaRouter.retrieve_authorized` under a simulated Viewer. On 27 author-written EN/KO/JA requests, lexical Top1 was **7/27**. On **8/9 Korean** and **7/9 Japanese** supported requests, the lexical Top-K all had **zero signal**. Some Top1 correctness is a catalog insertion-order accident.

Before claiming the opt-in real E5 model actually improves source-specific cross-lingual recall, compare it **on these same provider-authored contracts** rather than on only our synthetic 13→500 descriptions.

## Frozen source & CPU checkpoint

Provider source manifest: `benchmarks/open-meteo-openapi-real-source-dev-manifest.json`, nine original YAML byte-identities, attributed to Open-Meteo (CC BY 4.0). Model: [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) checkpoint **`fd1525a9fd15316a2d503bf26ab031a61d056e98`** (MIT). The model checkpoint itself, not a mutable `main` reference, is requested by `SentenceTransformer(revision=...,` CPU-only, `trust_remote_code=False`; installed from the official local Python open-source runtime. No LLM, paid inference or GPU.

## Exact provenance, trust boundary and experiment

1. Verify and parse nine *original external* YAML files into nine registered current typed OpenAPI endpoints, with failures aborting the model study rather than silently inventing a substitute fixture.
2. Configure **deny-by-default** `AuthorizationPolicy` permitting only the nine registered `open_meteo_*` GET routes for a **simulated Viewer**. For each prompt, call real `SchemaRouter.retrieve_authorized(..., k=9)` first, not a direct unscoped registry bypass. Fail closed unless that public result is an exact 9-route permutation of current authorized routes.
3. Pass **only these approved `CapabilityCandidate` descriptions** to `EmbeddingDecisionBackend(E5CachedEmbedder)` via bounded `DecisionRequest` and compare the same query's normal lexical and real locally computed E5 Top1/Top5. E5 query and passage prefixes are applied by the official optional adapter; passage embeddings are cacheable. No score cutoff is set.
4. The cohort is 27 supported and 9 unsupported **author-written** EN/KO/JA prompts. Report language-stratified Top1/Top5 source match, positive lexical score/zero-score fallback, provider SHA, pinned model revision and complete case rows, plus CPU memory and time.
5. Validate no unknown/denied ID, no tool invocation, positive/no-fit confusion. Because E5 unconditionally ranks nine candidates, a **negative query also returns a shortlist**; this is *not evidence of false execution* nor a calibrated no-fit gate. The baseline lexical `retrieve_authorized` **does not use this E5 rerank by default**: this is a controlled external optional stage, not a product patch.

## What this does NOT establish

Authentic provider-authored schemas from **one** provider, but all query labels are self-authored development material. No query-author-disjoint labels, live API invocation, independently verified host auth identity, field/argument accuracy, schema operation-fit reliability, real-agent task success or measured no-fit FPR. A positive result is **conditional candidate recall** on only nine routes, not 500 independent providers or an independent agent test. A negative result must be reported unmodified.

Results from current [#1438](https://github.com/JDeun/SchemaRouter/pull/1438) and [#1439](https://github.com/JDeun/SchemaRouter/pull/1439) freeze the prior Top10 score overlap and oracle upper bound on a distinct author-authored synthetic catalog; DO NOT pool denominators with the real Open-Meteo evaluation. No default product threshold, promoted model or release.

Commands on Ubuntu CPU:

    python -m pytest -q tests/test_research_real_open_meteo_e5_cpu_dev.py
    python -m scripts.research_real_open_meteo_e5_cpu_dev --manifest benchmarks/open-meteo-openapi-real-source-dev-manifest.json --source-dir artifacts/open-meteo-scoped-e5/source --output artifacts/open-meteo-scoped-e5/report.json

Dedicated read-only GitHub Actions CPU, 40-minute cap (model download + CPU inference), no GPU, outside tools, live provider call or release permission. **#1339 / #1346 OPEN; v0.18.0 #1356 HOLD.**

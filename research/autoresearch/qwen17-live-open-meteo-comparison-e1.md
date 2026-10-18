# Exact Qwen3-1.7B model substitution over original real Open-Meteo 2-hop E1

2026-10-18, issue #1477. Candidate model scale check **before outcome**, not a hyperparameter sweep or a new model-per-prompt variant.

## Prior measured baseline and exact comparison

[#1522](https://github.com/JDeun/SchemaRouter/pull/1522), real original-provider [Actions #39089681858](https://github.com/JDeun/SchemaRouter/actions/runs/39089681858): pinned Qwen3-0.6B original read-only Open-Meteo two-hop task with 3 researcher-authored, previously exposed EN/KO/JA inputs; 1/3 strict full success (KO), EN 1 geocoding then premature final; JA no real provider requests, host/native source denied. Actual source API state and final-answer matching enforced.

Change **only** frozen candidate model/tokenizer: `Qwen/Qwen3-1.7B` full Hugging Face SHA `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, Apache-2.0. Model generation method and parameters are inherited byte-for-byte from `scripts/agent_utility_v7_dev_agent.py::LocalQwenAgent.generate`, which the baseline uses. No prompt, tool definition, MAX_TURNS, JSON parser, actual authorized host adapter, registered source route ID, field scope, sequence requirement, Open-Meteo URL, scoring rubric, or denial behavior is modified: `scripts/research_real_qwen_open_meteo_two_hop_e1.py::evaluate` is directly reused.

The model resolves its source SHA via Hugging Face Hub and fails closed if it differs. Linux GitHub CPU with 4 Torch threads, fixed seed inherited from frozen baseline, and sufficient RAM/disk. No proprietary GPU or paid hosted inference.

## Strict per-language report

- Model-selected geocode call, actual source-geocoding host dispatch; then only the **exact actual projected source** latitude/longitude may lead to weather host execution; then strict model-generated `temperature_2m` / `unit` / `observed_at` matching second original provider output. No fallback, host repair or extra eligible route.
- Every incorrect/missing input, wrong route order, early final, failed native provider, malformed output or incorrect factual final stays a failed task. Summaries contain aggregate per-language host call counts, outcome reason, model/source identities and measured CPU time/RSS; no coordinates, temperatures or raw source data.
- 0.6B prior-run **1/3** and new candidate **0–3/3** must be reported, including negative outcomes. Dynamic weather and separate-run source availability are confounders; no significance or broader architecture superiority can be established from three exposed tasks.

This study may fail due to model-loading limits, external source availability or model errors; CI must NOT pass off missing evidence as a positive result.

## Explicit qualification boundary

These three multilingual inputs are developer-authored and had already been exposed repeatedly. They do not show native language understanding independently because the user messages contain source index names, language and country codes; no production no-fit or 500-tool K5 retrieval; no hidden multi-tenant rights cases. They are not independently created, originally publisher-authored, independently permission-verified gold, source-disjoint or unseen E2. **0/19 independently qualified E2, A02/R05 NOT_VERIFIED, default model and v0.18 #1356 HARD HOLD.** Even a 3/3 candidate score must not trigger release or model promotion.

Next source-disjoint study needs actual independent publisher-native task+reference, protected EN/KO/JA original requests, source permissions, supported/unsupported/missing/ambiguous labels, exact tool arguments, final-answer and denied-action evaluation.

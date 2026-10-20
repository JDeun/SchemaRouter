# Strictly opt-in fixed-K5 selector-order disclosure — E0 preregistration

**Owner:** #1477 (paired downstream usefulness), #1339 (multilingual retrieval), #1560 (native G5).  
**Evidence status:** source-scoped synthetic **E0 engineering only**. This document and unit tests do not measure model quality.

## Observed motivating mismatch (2026-10-20)

- In [Draft #1612](https://github.com/JDeun/SchemaRouter/pull/1612), the genuine pinned E5 candidate selector returns source-verified Top-5 **in semantic rank order**.
- The existing `run_generated_episode` sorts the selected route IDs by **lexical name** before calling the principal-scoped model tool serializer. Thus the ranker Top1 is *not* necessarily visible in the first tool position.
- Existing actual Qwen+E5 exposed synthetic DEV results show retrieval gains but continued downstream selection/unsupported no-call failures. These observations motivate, but do not prove, any rank-position effect.

## New isolated arm

`experimental_preserve_rank_order=True` in the **already existing** `run_generated_episode` `EVAL-FIXED5-OPTIN` condition:

1. Requires an explicit existing experimental selector **and** a principal-scoped `AuthorizedAgentToolSurface`; rejects nonboolean flags, unscoped selection and all frozen conditions.
2. Keeps selector-provided IDs, membership checks, duplicate checks, exact registry version, scoped authority revalidation, K≤5, typed disclosure and trusted `FrozenCorpusExecutor` unchanged.
3. Changes **only the visible order** of already-authorized candidates from alphabetic route name to selector order. No model-visible scores, independent labels, raw gold, new tool execution authority or automatic product promotion.
4. `False` is the default; all historical FULL/SR-5/SR-10/SR-PROGRESSIVE/ORACLE and existing opt-in semantics remain unchanged.

## Necessary actual-model A/B evidence *before claiming utility*

- Freeze a single genuine E5 model revision, Qwen revision, authorized source snapshot and exact same developer-authored task cohort; both arms must expose **the same Top-5 membership, schema definitions, policy identity and byte budget**.
- Compare A = default alphabetic display vs B = identical candidates in original E5 order. Counterbalance A/B execution position and seeds; do not select based on observed performance.
- Report real model-visible slot of the required endpoint and first attempted tool separately from **E5 similarity rank**. Record actual first attempted source operation, verified tool completion, supported task success, early final, unsupported tool attempted, strict unsupported no-call/refusal, tokens, CPU selection and full episode latency.
- Fail closed on source/permission drift and any unequal K or leaked hidden field; the experiment is rejected if the proposed arm increases unsafe exposure or changes source content.
- Interpret differences as exposed **synthetic DEV only**. Independent publisher authored source+gold and agent E2 under #1346/#1477 remain mandatory before production default or v0.18 release.

## Stop rules

If the exact same candidate content/order-controlled test does not improve actual downstream execution or has larger unsupported erroneous attempts, record the negative outcome and retire the hypothesis. Never confuse the number of tool attempts with grounded final-answer correctness. Frozen #432 results and #1356 release HARD HOLD remain unchanged.

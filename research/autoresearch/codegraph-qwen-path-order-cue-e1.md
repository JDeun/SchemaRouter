# Surgical G5 path-order cue — separate pinned local Qwen E1

**2026-10-23 · #1723 / #1711 · preregistered before the first treated model run · research-only**

## Actual-model trigger and held control

The previous unchanged four-route K5 local source study
[#1732, run #39949700021](https://github.com/JDeun/SchemaRouter/actions/runs/39949700021)
ran *real pinned local inference* for Qwen3-0.6B and Qwen3-1.7B,
EN/KO/JA. Qwen3-1.7B **3/3** accepted one non-executing host-scoped
schema request but its first native call was refused by the unchanged
host as `unsupported_bound_path`: no prefix of an approved ordered G5
route set matched the requested first route; zero original callbacks.
Qwen3-0.6B **3/3** prematurely finalized, even when KO/JA had one
materialized schema. Surgical strict final success was **0/6**, not an
infra failure. Paired unchanged 1.7B FULL and lexical controls each
completed EN/KO **2/3**, with JA final incorrect; typed G5 was **0/6**.
The `unsupported_bound_path` label does not contain raw route IDs,
refused argument names, values or model text, and does not justify
repairing untrusted actions. #1732 remains the immutable previous
control and original negative result.

## A single model-only intervention

**Hypothesis:** the model may need explicit instruction that
`route_sets[*].route_ids` is an *execution order*, not an unordered menu.
The model currently sees the source-attested path reference and later
receives original definitions, but on Qwen1.7B chose the wrong starting
route in every tested language. A fixed generic cue may cause it to
call the producer source first, then the consumer with the verified
preceding host observation, without any host action repair.

Register `--experimental-graph-path-order-prompt` as one isolated
opt-in addition to `--experimental-single-step-prompt` plus
`--experimental-bare-schema-request`. Only the **surgical** model system
prompt receives `GRAPH_PATH_ORDER_CUE_E1`; the text contains no specific
routes, arguments, gold, hidden inputs, source values or provider output.
FULL, lexical K5 and typed G5 prompts, exposure and scoring remain
byte-identical to #1732; **do not** combine with G5 continuation cue,
bare native JSON normalization or altered route inventory.

The host still enforces:

- Original four registered owner-reviewed read-only routes, identical
  fingerprint/authorization/scope/principal; strict K=5, no over-K
  batching and no new production API or executor.
- Only a model-chosen currently scoped *reserved schema request* may be
  normalized. It never executes the provider. Native original tool calls
  remain model-chosen, strict-parsed and independently checked against
  the live source-attested path prefix and host-bound observations.
- Five maximum model turns, all input/output/schema tokens included,
  independent correct-final oracle, no fabricated callbacks, no log of
  model output or source arguments; fixed diagnostic category labels only.

## Pinned matrix and decision

Run six fresh Linux CPU jobs, immutable Qwen3-0.6B
`c1899de289a04d12100db370d81485cdf75e47ca` and Qwen3-1.7B
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, EN/KO/JA, identical
query/source/principal/seed and four FULL/lexical/G5/surgical arms.
Keep a denominator of **one owner-authored translated task per model
and language**, strict full 2-hop task completion as the primary metric,
and record call count, schema requests, refusals, turns, tokens and
structural/argument-alignment labels. Compare to #1732 actual pinned
results rather than rewriting old files, changing scoring or claiming
that an experimental cue proves CodeGraph indexing caused token savings.

Success in a treated surgical row requires *two genuine original source
callbacks in dependency order* and an independently correct final
answer. Zero success is a valid scientific outcome; if the cue fails,
**stop iterating similar prompt wording** and consider a distinct,
separately reviewed Graph Frontier design. Even a local success is only
an E1 model-prompt result, not E2, provider consent/entitlement,
production promotion or authority to lift [#1356](https://github.com/JDeun/SchemaRouter/issues/1356)
HARD HOLD / [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)
external confirmation requirements.

## Actual six-cell result — after the preregistration above

The pinned GitHub Linux E1
[#39952057039](https://github.com/JDeun/SchemaRouter/actions/runs/39952057039)
completed **all six** real-model jobs on the exact preregistered code
commit `7242b20dd2353c47c3613fb94311ac2f7886a2fb`.
Workflow success indicates scripts ran; full-task success is a separate
outcome below. This post hoc result section does not alter the old
scientific controls or preregistered scorer.

| Pinned model | Lang | FULL/lexical exact task | Surgical path-order exact task | Surgical schema requests | Surgical original calls | FULL tokens | Surgical tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B | EN | false / false | false | 0 | 0 | 677 | 1,012 |
| Qwen3-0.6B | KO | false / false | false | 1 | 0 | 678 | 2,410 |
| Qwen3-0.6B | JA | false / false | false | 1 | 0 | 678 | 2,404 |
| Qwen3-1.7B | EN | true / true | **true** | 1 | **2** | 2,142 | 5,359 |
| Qwen3-1.7B | KO | true / true | **true** | 1 | **2** | 2,145 | 5,363 |
| Qwen3-1.7B | JA | false / false | **true** | 1 | **2** | 2,151 | 5,363 |

Strict surgical success: **1.7B 3/3**, vs its matched #1732 pre-cue
**0/3** and same-run FULL/lexical **2/3**. All three successful
surgical cells finished only after **two real original read-only host
callbacks**, with no unbound argument labels and an independently
correct final. Qwen0.6B remained **0/3** (premature final); it did not
gain a real native call in the surgical arm. Typed G5 same-run controls
remained **0/6** despite a single original call per cell.

**Tradeoff:** the 1.7B successful surgical path costs approximately
**2.5× the FULL model tokens** (~5.36k vs ~2.14k) on these local tasks.
The extra schema-request/model turns are included; a lower initial
schema payload does not constitute net cost savings. This is promising
model-protocol *correctness recovery* but **not** an evidenced CodeGraph
index cost benefit, not independent E2 and not release-ready. With a
single owner-created translated task per language, 3/3 is not a
population accuracy estimate. The next separately reviewed architectural
question is whether an authorized Graph Frontier can constrain current
offered definitions and reduce prompt/turn cost while preserving exact
source verification and the same task oracle. No silent migration from
this prompt E1 to a default or release is authorized.

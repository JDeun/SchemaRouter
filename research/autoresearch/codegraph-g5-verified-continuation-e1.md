# G5 verified first-read continuation: opt-in source-bound E1

**2026-10-23 · #1723 · local registered source, pinned Qwen E1 only · not E2**

## Motivating observation and falsifiable claim

[Exact-head prior single-step prompt model run #39930411562](https://github.com/JDeun/SchemaRouter/actions/runs/39930411562)
showed a common structural G5 failure: both pinned Qwen3-0.6B and
Qwen3-1.7B made **one genuine original native call** in EN/KO/JA G5, then
prematurely finalized without the dependent original read. For Qwen3-1.7B
EN/KO, under that same generic single-action prompt, independent FULL
and Lexical K5 arms completed both original reads and the strict final
answer, but G5 did not. Surgical CodeGraph remained at zero original
reads. This is a narrow source-path continuation defect, **not a search
index latency defect**.

The preregistered hypothesis: A minimal **host-verified source-progress
cue delivered only after an actual successful first G5 read** may prevent
a premature final and encourage a properly bound second read, with no
task-specific oracle information. An unchanged or invalid second action
is evidence **against** this hypothesis. No result is pre-asserted.

## Isolated intervention

An explicit local E1-only `--experimental-g5-verified-continuation` flag
is permitted only for **four registered read-only original routes**,
the joined fixture, and no other concurrent prompt/grammar treatment.

- FULL, Lexical K5, and surgical G5 run the **unchanged original**
  study implementation, prompts, strict parser, native executor and
  scorer. Only `concept_graph_optin` can receive this cue.
- The first, original, scoped native callback must have actually
  returned `status=ok` via the pre-existing read-only executor,
  passed output checks, and incremented the trusted source-call log.
  Additionally the dependent original route must still be in the
  currently authorized host-provided offered route menu.
- Only then, **after the real tool observation** and before the next
  model generation, append one statically defined generic user message:
  the authorized source path is not complete; select one currently
  offered next read-only tool only if its parameters are supported
  by the verified prior observation; never invent results or arguments.
- The cue contains **no gold, private parameters, route IDs, names,
  desired final answer, hidden fields or invented observation values**.
  It is not a synthetic tool call, response, guessed argument source,
  parser repair, auto-retry or alternate executor. It is a new
  **model-input treatment**, never a product default.
- The original `parse_one_model_action`, bound argument comparison,
  scope/authorization, live source witness and route order remain
  unchanged, as do fixed Qwen model revision, temperature-free
  decoding, original four source identities, EN/KO/JA queries, and
  at most five real model turns.
- There is at most one cue: `verified_continuation_cues` is a count
  0 or 1, reported only on the G5 arm. Other arms' prompt inputs
  remain untouched. The new cohort is labeled
  `AFTER_VERIFIED_FIRST_G5_CALL` and never pooled with the previous
  [bare-JSON adapter](codegraph-qwen-strict-bare-native-e1.md) or
  [static single-step prompt](codegraph-qwen-single-step-prompt-e1.md).

## Measured acceptance, safety checks and limitations

1. Test the *same original author-declared, four-route local source*,
   one task per arm/language, in pinned public Qwen3-0.6B and separately
   Qwen3-1.7B × EN/KO/JA on GitHub Linux CPU. All model generations,
   tool responses and token receipts are actual (not stub successes).
2. Primary outcome is a **strict complete two-hop task**, requiring
   both distinct original native read-only callbacks in dependency order
   with valid host-observation bound arguments and a correct final
   `case_state` JSON. A cue, parser-accepted envelope or second model
   turn is **not** success.
3. Measure source calls, model turns, cue count and total input+output
   tokens inclusive of the added turn content, separately per arm;
   emit allowlisted structural categories only, not raw generated
   text, source data, model thoughts, arguments or private auth.
4. Regression asserts no cue before successful original first native
   callback, no cue on other arms, no cue in blocked or mixed
   interventions, no source/callback/scorer drift, and no unexpected
   weakening of K5. Denied/no-fit/over-K remain fail-closed.

This is an **E1 synthetic local-source** test; language translations
are not independent cases, and any measured local success is neither
publisher-authored independent E2 (#1346) nor production cost/quality
evidence. #1356 v0.18 remains HARD HOLD. The current index p95 result
of #1560 is independent of any model task success.

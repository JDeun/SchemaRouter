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

**Amendment after an initially non-triggering matrix**: The first
implementation ran the G5 cue against the original default prompt,
which did not reliably perform an initial source read (e.g. pinned
Qwen3-0.6B KO actually made 0 native calls, cue count 0 in [run
#39932600124](https://github.com/JDeun/SchemaRouter/actions/runs/39932600124)).
That *cannot test* a treatment delivered only after a verified read.
The amended primary comparison therefore fixes the **already-measured
single-step system prompt** (#1728, run #39930411562) for both baseline
and cue-treated model calls and adds the G5 cue **only as a second-stage
incremental intervention**. The original zero-cue run remains recorded,
not overwritten or interpreted as evidence against a triggered cue.
No task-specific gold was consulted when making this amendment.

An explicit local E1-only `--experimental-g5-verified-continuation` flag
is permitted only for **four registered read-only original routes**,
the joined fixture, with the preregistered **single-step system prompt**
already active. The separate bare-JSON grammar variant remains forbidden
as a simultaneous treatment.

- FULL, Lexical K5 and surgical G5 receive the **same fixed
  one-action-per-turn system prompt** as in the existing #1728 E1 study,
  with unchanged strict parser, native executor, source and scorer.
  The G5 arm receives that identical system prompt **plus** the
  post-verified-first-callback cue. Only `concept_graph_optin` can
  receive the additional cue; its incremental effect is assessed
  against #1728's *G5 arm*, not against a default no-prompt run.
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
  `AFTER_VERIFIED_FIRST_G5_CALL` **on top of**
  `EXACTLY_ONE_NATIVE_ACTION_PER_TURN`. It is NOT pooled with the
  independent [bare-JSON adapter](codegraph-qwen-strict-bare-native-e1.md);
  the fixed [single-step prompt](codegraph-qwen-single-step-prompt-e1.md)
  is instead the explicit matched base cohort.

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

## Historical first pilot: no treatment actually delivered

Before the matched single-step baseline was mandated, the six pinned
real-model source-local jobs in [run #39932600124](https://github.com/JDeun/SchemaRouter/actions/runs/39932600124)
finished SUCCESS *operationally*, but **all six** G5 experiments recorded
`verified_continuation_cues=0`: no original first native callback was
executed by G5 in the no-single-step-prompt cohort. Accordingly all
six G5 tasks failed (0/1 each); this is a **non-triggered intervention**
and must **not** be scored as a negative cue effect.

For the Qwen3-1.7B KO historical control, FULL and lexical each made
one original call then stopped; in every other listed arm/language there
were zero original calls. The model did not provide a valid first
G5 source observation, so the host's safety gate properly abstained
from appending any cue. Preserve those source-grounded null-exposure
results separately from the **amended run**, which has the previously
validated #1728 single-step system prompt active in *both* original
and extra-cue conditions. Compare only matching model revisions,
source fingerprints, prompts, original executor, five-turn cap and task
gold. Any positive result would be a *second-stage progress cue*
effect in this author-prepared E1 fixture, not overall CodeGraph
superiority or independent E2.

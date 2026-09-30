# 0.14 successor development screen for output-field projection

Tracking issue: **#510**

## Why this exists

The [output-field projection](field-projection-answer-quality.md) development
screen produced a null result: every factual metric was 0.0000 in every
condition, the comparator included. The cause was not the hypothesis. From the
shard rows, `tool_call_count = 0` and mean `turns = 1.21` — the frozen B1 agent
skipped tool use and fabricated an answer envelope from the tool's own name.

Narrowing further: B1 reached 68–91% task pass on that same runtime and harness
with `SYSTEM_PROMPT`. The projection screen uses `FINAL_SYSTEM_PROMPT`, which
additionally demands a structured answer envelope. So:

> Qwen3-0.6B can do tool-calling **or** a structured answer envelope, not both.

Relaxing the prompt and re-running the same corpus is what #506's Option A
governance forbids — `prompt or harness semantics` is on its frozen list. The
sanctioned path is this one: close the screen as consumed and preregister a
successor with its own query-disjoint surface.

## Instrument eligibility

The instrument is chosen by a gate frozen **before** any candidate runs, because
running the roster and keeping the best performer would be choosing the
instrument by its outcome — the same error one level up.

| Criterion | Threshold |
| --- | ---: |
| episodes emitting a valid answer envelope | ≥ 80% |
| episodes making at least one tool call | ≥ 90% |
| episodes whose answer contains at least one observation-grounded fact | ≥ 70% |

The third criterion catches a runtime that calls tools and still grounds
nothing — envelopes present, tool calls present, but nothing in the answer
traces back to an observation.

Roster, ordered and frozen:

1. `HuggingFaceTB/SmolLM3-3B`
2. `Qwen/Qwen3-4B`
3. `Qwen/Qwen3-8B`

The **first** candidate that qualifies is used; later candidates are not run.
Choosing among qualifiers would select the instrument by its outcome, which is
the error this gate exists to prevent.

`select_runtime` in `scripts/qualify_agent_utility_runtime.py` encodes that
rule: it walks the roster in its frozen order, returns the first qualifier even
when a later candidate scores higher, and refuses results that were produced out
of order. It returns `None` both when no candidate has qualified yet and when
the roster is finished without one — only the second is a verdict, which is why
`roster_exhausted` has to be consulted before reporting that no candidate
qualified.

**The rule is enforced only where that function is used.** The screen's
evaluation workflow is not written yet, so nothing calls it today. Whoever
writes that workflow must route the selection through `select_runtime` rather
than reimplementing the comparison, or the ordering guarantee is prose again.

Qualification is meant to run on its own surface, separate from both the #506
corpus and this experiment's, with its numbers treated as evidence about the
instrument and never reported as experiment evidence. **That surface does not
exist yet.** There is no generator, no corpus, and no runner for it — only the
gate (`scripts/qualify_agent_utility_runtime.py`) that will score whatever
rows it is eventually given.

### Recorded trade-off

`SmolLM3-3B` is also the confirmation arm's runtime, so the screen and the
confirmation differ only by surface. Accepted deliberately: B2's canonical run
already shows this model performs the tool-calling task, making it the candidate
most likely to qualify first, and a screen that cannot qualify is worth nothing.
The screen's surface is query-disjoint, so it does not consume the confirmation
surface.

## What is identical to #506

The four conditions, six distractor strata, six languages, separately reported
metrics, paired cluster bootstrap and promotion gate are unchanged, so results
stay comparable. Only the **runtime** and the **surface** differ.

## Query disjointness

Enforced at generation, not left to a test. `build_corpus` raises before writing
anything if the surface shares a normalised query with any prior surface. The
#506 projection corpus is checked directly — built locally inside the
generator rather than registered in `scripts/agent_utility_prior_query_guard.py`.
Registering it there would change `known_prior_query_manifest()["union_sha256"]`,
which is stamped into generated v3/v4/v6 corpora and hard-checked by their
validators; a stored corpus artifact created before this branch must still
validate against main, so that registration was reverted in favour of the
local check.

**What "disjoint" means here, recorded plainly:** this surface is the #506
corpus under a distinct identifier space (`S####` in place of `P####`) —
every task is byte-identical to its #506 counterpart apart from that prefix.
Disjointness means no shared *query string*, nothing more; it is not a
content-independent surface. That is judged acceptable because #506's screen
never called a tool, so no observation content from that corpus ever reached
a model, and nothing in this pipeline trains on prior runs. Issue #510's
letter — "not one query shared" — is met; the surface is not "genuinely
different" content.

## Governance

This screen remains development evidence. It may not be reported as
confirmation, and it may not change conditions, task content, distractor strata,
thresholds, the scorer, prompt or harness semantics, or row inclusion. #506's
corpus, conditions, gate and confirmation arm are untouched.

If no candidate qualifies, that is recorded as a terminal result about the
screening approach — not as a reason to weaken the thresholds.

## Reproduction

```bash
python scripts/generate_agent_utility_v8_successor_corpus.py \
  --source-revision "$(git rev-parse HEAD)" \
  --out artifacts/successor/successor-corpus.json

python scripts/validate_agent_utility_v8_successor_corpus.py \
  --corpus artifacts/successor/successor-corpus.json
```

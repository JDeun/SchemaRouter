# Separate tool-fixture completion from observed assistant final turn (E0)

**2026-10-17.** Issue #1477, continuation of merged local real-Qwen
agent fixture pilot #1490 and the supported/OOD diagnostics of #1491.

The original `run_generated_episode` task-pass verdict for a supported
fixture is `FrozenCorpusExecutor.complete and not context_overflow`.
That proves the deterministic synthetic tool steps were consumed but
**does not imply that the agent issued a final answer afterward**, let
alone a correct factual final answer grounded to a native provider.

This additive, post-execution-only extension to the existing sanitized
`E0_SYNTHETIC_DEV_ONLY` task witness exports three separate booleans:

- `agent_final_turn_observed`: the last structurally recorded agent
  turn had event `final`. It is **not** a verifier of generated text.
- `supported_final_after_fixture_completion_observed`: the
  synthetic task is supported, executor marked complete, and the final
  event was observed; neither gold nor generated text is released.
- `actual_final_answer_correctness_measured=false` unconditionally.
  Real-world fact correctness and evidence citations are not measured.

We explicitly leave original `passed`, `task_complete`, K5, catalog
authorization and historical score semantics untouched. This is an
additional diagnostic, not a backdated relabel or a claim that synthetic
fixture pass equals factual correctness. The grade is computed only
after model execution by an allowlisted trace serializer. No route
IDs, fixture gold, raw queries, model responses, hidden output values
or complete tool-call transcripts appear in public JSONL.

Tests distinguish (a) synthetic supported tool completion **without**
an observed final, (b) synthetic completion followed by final, (c)
unsupported final/refusal, (d) structurally malformed turn evidence,
and (e) private generated text redaction. Existing #432 historical
outcomes are not modified. #1346 independently authored real native
agent task/gold remains BLOCKED_EXTERNAL and #1356 v0.18 release is
HARD HOLD. The prior pilot #1490/diagnostic #1491 E0 cannot be
promoted to independent E2 by this additional boolean.

## Real local-model diagnostic integration

The post-execution `summarize_fixture_safety_strata` scorer now consumes
these optional E0 flags. If a legacy synthetic row cohort entirely lacks
them, each new count is **null (unmeasured), never an inferred failure
or a successful final answer**. If only some tasks in an arm provide
them, or boolean flags contradict the original supported/task-complete/
final-event state, it fails closed. New real-model runs publish separate
counts for completed supported fixture **with** a final turn, completed
fixture **without** one, and unsupported final-turn events (which do not
prove correct refusal).

The dedicated Qwen3-0.6B + E5 Linux CPU workflow now reruns the identical
12 already-disclosed synthetic EN/KO/JA tasks and prints these metrics
beside (not instead of) existing strict no-call/OOD errors. The existing
published 2/12 vs 6/12 aggregate task-pass denominator, executable
policy boundaries, all old frozen evidence and Release HOLD are unchanged.


## 2026-10-21 — progressed synthetic step witness (additive, E0)

The original `passed` and `supported_final_after_fixture_completion_observed`
are intentionally retained, but their structural truth values **do not
independently show a performed tool call**. A source/test row may claim the
fixture complete and show a final turn with no matching attempt record.

The additional
`supported_final_after_progressed_fixture_step_observed` field is true
**only if** the existing supported/fixture-passed/final-turn flags are true,
the context did not overflow, the post-execution `tool_call_count` is a
positive exact match to both serialized per-turn tool calls and raw trusted
grader attempt rows, all serialized attempt receipts match their raw attempt,
and at least one expected, policy-allowed, schema-valid, semantically-valid,
error-free attempt advanced the synthetic fixture. The raw route/arguments,
attempt receipt, original query and expected gold remain private; public JSONL
contains only the new boolean.

The existing tiny EN/KO/JA E0 safety-strata aggregator counts that stricter
evidence separately as `supported_final_with_progressed_fixture_step` when
the entire arm has complete, consistent flags. Legacy absent fields yield
`null`, never an inferred success; partial/malformed evidence is rejected.
This is **not** a live provider call, independent agent E2, fact correctness,
a calibrated no-fit rate or grounds for v0.18 release.

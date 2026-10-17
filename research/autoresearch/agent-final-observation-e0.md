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

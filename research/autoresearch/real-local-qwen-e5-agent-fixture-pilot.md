# First actual local agent + real E5 fixed-K5 task-fixture DEV pilot

**2026-10-17, owner issue #1477.** This is an explicitly **E0/dev** bridge from
retrieval accuracy to *agent-generated* tool-use completion; it is **not**
publisher-native provider execution, independent E2, calibrated no-fit or
commercial-equivalence evidence.

## Frozen prior-to-inference design

The exact, previously published source is
`benchmarks/multilingual-embedding-cpu-dev-20261015.json`. The original
84 tasks, 13 read-only native endpoints and corpus SHA256 are revalidated
before selection. **No new hidden / query-disjoint task cohort is claimed**.

Twelve preselected original task IDs are identical across EN/KO/JA:
- supported `materials.search` (one-step read-only fixture, no arguments)
- supported `weather.current` (one-step read-only fixture, no arguments)
- unsupported `materials.delete_sample` (no registered delete tool)
- unsupported `calendar.create_event` (no registered create tool)

The 12 cases are **six supported + six unsupported**, four per language.
This deliberately small unscored engineering pilot measures whether the
real agent generates the expected tool-call *format*, invokes one
visible route in the existing frozen executor, and returns the exact
`REQUEST_MORE_TOOLS` on unsupported cases; it does not establish
broad heterogeneous task success, argument/field correctness or
real world answers. The trusted fixture returns only a synthetic
`status=ok` observation, with no actual weather/material measurement.

Three arms share the **same source router**, original query, explicit
principal and K=5:
1. `lexical_k5` — real native `SchemaRouter.retrieve_authorized`;
2. `e5_k5` — real pinned CPU `intfloat/multilingual-e5-small` and
   request-local checked native tool surface;
3. `hybrid_k5` — predeclared RRF60 lexical+E5 on the same visible source.

The agent is the **existing pinned local Qwen3-0.6B** from
`scripts/agent_utility_v7_dev_agent.py` at revision
`c1899de289a04d12100db370d81485cdf75e47ca`,
float32 CPU, greedy decoding, existing model/runtime configuration.
The E5 revision remains
`fd1525a9fd15316a2d503bf26ab031a61d056e98`.
The task loop and grading reuse
`agent_utility_generated_common.run_generated_episode` and
`FrozenCorpusExecutor`, **not a new model agent implementation or scorer**.

Every arm has identical user query, frozen evaluator and system prompt.
The selector receives ONLY original query and authorized native source IDs;
gold/executor state remain in the trusted harness and are never in
model/selector input. The existing principal-scoped surface enforces
HMAC source-view integrity after #1488, hidden-field projection, bounded
model-visible schema, query/principal identity, candidate K5 and source
fingerprint checks. A denied or mutated call MUST never run an unauthorized
native provider; this harness invokes NO actual external provider.

## Reporting and strict provenance

The existing `E0TraceProvenance` + `sanitized_e0_trace` emit a
per-task keyed HMAC identity (secret generated at runtime and never
exported) with outcome, attempted tool count, token totals, stage
evidence and time. The private fixture, raw query, complete outputs,
arguments, model responses, task ID/gold, HMAC key and chain-of-thought
are **never published**. The existing
`research_paired_agent_fixed5_e0.aggregate_paired_e0`
checks identical task/source/model/hardware/seed/K cohorts, requires
zero unauthorized destructive executions and calls the original
task-stratified bootstrap. Report grouped task pass and EN/KO/JA
strata alongside unsupported attempted-tool evidence.

The injectable programmatic path always labels itself
`UNATTESTED_AGENT_AND_BACKEND_E0_DEV_ONLY` and indicates real
model generation/inference **false**, even when supplied with
sophisticated mocks. Only CLI mode `--mode real-cpu` loads **both**
local pinned model checkpoints and marks
`REAL_LOCAL_QWEN_E5_FIXTURE_TASK_DEV_ONLY`.
The scored result is *fixture task completion* as defined by the
original executor, not native provider results or verified factual
final-answer correctness. This pilot is intentionally not a
production noninferiority gate and cannot clear v0.18.0 HOLD.

## Exit

This pilot can identify agent format/abstention limitations and
end-to-end synthetic tool-call throughput, but its 12 exposed tasks
are too small and simple to certify multilingual performance.
Independent publisher-authored source/tasks/permission labels (#1346),
real native provider outcomes, multi-step argument/output state fit,
and prospective no-fit calibration are required before integrated
E2 or release quality can be assessed. Historical #432 negatives and
v0.18 (#1356) HARD HOLD remain unchanged.

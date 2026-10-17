# Real local Qwen3-0.6B × native E5 K5 paired agent task-completion E0 DEV

**Issue #1477, 2026-10-17.** Unlike the prior retrieval-only E5
benchmarks, this experiment actually loads two pinned local CPU models
and runs the repository's **existing tool-using agent episode loop**,
including model-generated tool-call text, original tool-call JSON parsing,
typed executor fixture arguments/state, source-scoped model-visible
observations and final task-completion adjudication.

**It is still NOT independent E2** and does not invoke any real external
provider or offer a calibrated no-fit decision.

## Precommitted six cases (selection frozen before inference)

Exactly 6 **previously published** tasks are selected from the
2026-10-15 synthetic DEV corpus, unchanged. One supported and one
unsupported request per EN/KO/JA language:

| Language | Supported | Unsupported |
|---|---|---|
| en | weather.current | materials.delete_sample |
| ko | inventory.lookup | calendar.create_event |
| ja | papers.search | flights.book_ticket |

All queries are original, case-sensitive unmodified source bytes, with
the same SHA256 verifier as previous real-E5 run. The original native
13 read-only tools, scope and original principal are used for *each*
arm and task. No Gold or task step fixture enters the model or candidate
selector. Grader-only one-step supported fixtures carry no required
arguments and produce a deterministic coarse `{"status":"ok"}` receipt.
Unsupported fixtures have no executable expected step; the episode must
make **no executable tool call and reply exactly
`REQUEST_MORE_TOOLS`** to count as passing. This does not prove that
real weather/inventory/paper providers would answer or that a full user
answer is factually correct.

Fixed candidate-selection arms: original
`SchemaRouter.retrieve_authorized` lexical K5; opt-in pinned
`intfloat/multilingual-e5-small`
`fd1525a9fd15316a2d503bf26ab031a61d056e98` K5; opt-in
RRF(60) hybrid K5 built on the same source. The same frozen
`scripts/agent_utility_v7_dev_agent.py::LocalQwenAgent`
`Qwen/Qwen3-0.6B` at pinned revision
`c1899de289a04d12100db370d81485cdf75e47ca` emits actual
tool-call generations for all arms on GitHub Actions Ubuntu CPU,
`SEED=20260929`, 4 threads, original 6-turn/256-token bound.
Existing `run_generated_episode` and `FrozenCorpusExecutor` perform
the agent loop and grading; **no new evaluator, new parser or
gold-aware recovery rules** are introduced.

## Provenance, security and falsification controls

- Enforce exact original full-corpus byte digest/content; predeclared
  split commitment; six unique cases and exactly one supported/OOD per
  language. 18 agent episodes total, same agent instance across arms.
- Only trusted principal-scoped authorized model route descriptions and
  max five scoped tool definitions are exposed; only read-only native
  operations. Source registry/policy/principal and sealed model-view
  receipts rechecked continuously. No unauthorized mutation or new
  executor invoked.
- Private per-run HMAC protects task identities in the post-execution
  `sanitized_e0_trace`; only aggregate token/latency/pass/stage
  metrics escape. No original raw queries, private arguments, Gold,
  model reasoning or full tool outputs are exported.
- Aggregate with **existing** `research_paired_agent_fixed5_e0`
  paired task/stratum×language bootstrap reporter. Tiny strata (one
  supported and one unsupported per language) make bootstrap
  intervals **not representative** of model quality outside this
  exact set.
- Injected fake agents/backends are always
  `E0_SYNTHETIC_DEV_ONLY` and both real model flags false, even if
  synthetic episodes pass. Only the explicit CLI branch that loads
  the actual Qwen and E5 pinned weights on local CPU may label a run
  `REAL_QWEN_E5_AGENT_SYNTHETIC_E0_DEV_ONLY`.
- Fail closed on source/policy drift, mismatched model selections, any
  unauthorized destructive action, incomplete paired cohorts or
  malformed privacy artifacts. A model that refuses a supported task
  is scored **failed**, not silently repaired. A legitimate out-of-scope
  generated provider call may trigger a protected-source abort; report
  this blocker rather than invent task completion. This report
  distinguishes an unsupported *retrieval candidate* from an actual
  unsupported executable *tool call*.

## Run and evidence limits

```bash
python -m scripts.research_real_qwen_e5_agent_paired_e0 --mode validate
python -m scripts.research_real_qwen_e5_agent_paired_e0 \
  --mode real-cpu --out artifacts/real-qwen-agent-e5-e0/report.json
```

Local CPU hardware and pinned agent/retriever weights, token counts,
final fixture task-pass, unsafe calls, per-language and per-condition
results are retained. This E0 pilot has only **3 supported/3
unsupported** tests and cannot establish independent E2, provider
end-to-end correctness, safe no-fit calibration, statistical
superiority, commercial quality, or user-facing SLA. Do not change
the default product, tune on these shown tasks or alter frozen #432.
The full prospective publisher-authorized #1346 task/source cohort
and broader same-agent real external tool execution remain blocked.
v0.18.0 #1356 **HARD HOLD** remains unchanged.

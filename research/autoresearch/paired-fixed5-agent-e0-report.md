# Opt-in paired fixed-K5 agent success analysis — E0-only

**Status:** Engineering evaluation plumbing, not a measured independent task
study, product decision, confidence of generalization, or v0.18 release gate.

## The missing piece addressed in #1477

Merging PRs #1479/#1480/#1481 made it possible to invoke a principal-scoped
synthetic agent episode through a non-executable semantic backend and obtain a
sanitized post-execution trace. The next task is to report *paired actual task
completion* once legitimate comparable outputs have been collected, rather
than presenting route-recall on exposed DEV requests as agent success.

`scripts/research_paired_agent_fixed5_e0.py` consumes exactly three external
**caller-supplied** arm receipts named `lexical_k5`, `e5_k5`,
`hybrid_k5`, and one HMAC-identified trusted task manifest. This component
**does not run the agent**, choose tools or generate new cases.

The manifest and each arm must match exactly on frozen source SHA/revision,
split SHA/name, pinned model revision/runtime, hardware class, seed and K=5.
All run rows must be the original safe `e0-stage-observations-v1` schema
from #1480. The component rejects missing/duplicate task IDs, unsupported
language or supported-label drift, invalid candidate exposure, unsafe
destructive execution, nonfinite/negative telemetry or unpaired results.
The task HMAC is the unit of analysis, never an exposed original query.
A missing E5/hybrid arm fails closed, not silently replaced with lexical
results. Arm labels are trusted receipt labels and are **not independently
cryptographically attested**; separate source-verified tracking is required.

The analysis **reuses** the preregistered frozen #432
`_paired_stratified_bootstrap` algorithm (seed 20260929; 10k replicates;
task identity clusters, task stratum × language), without changing old
#432 outcomes. It reports primary synthetic task completion by arm, paired
pass-rate differences versus lexical, 95% paired bootstrap intervals,
EN/KO/JA pass rates, observed unsupported tool executions, exposed tool
schema tokens and input tokens, selection/episode latency means, and
violations (hard-stop on nonzero unsafe destructive execution).

## Crucial explicit limitations

- All unit-test outcome scores are **constructed canary fixtures** for
  validating comparability and privacy; none are results of a real
  E5 or Hybrid model.
- The safe E0 projection only exposes candidate counts, not route/field
  identities; it cannot compute route-set, field, parameter or operation
  recall. It does not independently witness genuine provider execution.
- E0 reports always contain
  `independent_e2_qualified: false`,
  `publication_gate_passed: false` and
  `decision: E0_DESCRIPTIVE_ONLY_NOT_INDEPENDENT_E2` even if all
  test tasks pass. Model/hardware/split/source declarations require separate
  verification by the actual run harness and third-party case author.
- Future #1346 case intake must freeze exact external native source bytes,
  independently authored EN/KO/JA/OOD/forbidden task identities and labels,
  provenance/permissions and disjoint splits **before scoring**. Integrate
  actual model execution and source/host receipts then; do not relabel
  these E0 synth receipts as E2 post hoc.
- The current component keeps three fixed-K alternatives comparable;
  FULL and ORACLE are separate diagnostic conditions, not misidentified
  as K=5 competitors. It does not promote any product retrieval default.
- No proprietary host, hidden principal payload, gold fixture, raw model
  output or chain of thought enters the serialized public summary.

Reproduction with already collected approved E0 receipts:

```bash
python -m scripts.research_paired_agent_fixed5_e0 \
  --manifest private-frozen-synthetic-manifest.json \
  --runs private-scoped-e0-arm-receipts.json \
  --out paired-e0-summary.json
```

Missing source/task receipts are **BLOCKED_EXTERNAL / NOT_RUN**; never fabricate
them to produce an apparent improvement. Historical #432 and release #1356
HARD HOLD remain untouched.

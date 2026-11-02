# Algorithm 1 A10 — source-pinned no-fit evaluation (E0 design)

**2026-10-26.** Build an offline evaluator on the existing five-byte-stream
native E2 intake. It consumes *observed* paper plan statuses from the original
run, not model-authored gold or a synthesized inference threshold. Original
publisher data are not available locally, so all local fixtures remain E0.

## Boundary and choice

- Reuse `inspect_source_pinned_native_cohort` to bind manifest, case, gold,
  development and native inventory verbatim bytes; reject all mismatches.
- Require a complete, exactly paired outcome set with strict status taxonomy.
  Never accept model-generated gold or non-source-backed extra cases.
- Report EN/KO/JA supported false refusal, unsupported false accept, deferred,
  ambiguity and unknown separately. `no_proven_hit` means insufficient proof
  within the current source view, **never** global capability absence.
- Optionally admit exact **host-observed** nonnegative agent tool-attempt
  counters per case. Missing counters remain unknown, never zero; observed
  unsupported dispatch and agent dispatch despite plan abstention are separate
  diagnostics. The rate denominator is only actually observed cases. A
  diagnostic `candidate_within_declared_limits` is **null** until every case
  has a host counter; unsafe unsupported/nonbinary calls, post-abstain calls
  and supported offers with no observed dispatch prevent a passing diagnostic.
  The distinct `plan_within_declared_limits` is planning-only and cannot
  represent task success or a production qualification.
- The existing A7 paired-run result carries a `Decision` but not the exact
  original paper plan `status`. An explicit A7→A10 adapter may project this
  decision and observed host `tool_call_count` into a case observation. It must
  translate `abstain` to **`abstain_unclassified`**, not `no_proven_hit`;
  the independent coordinator remains responsible for joining the exact
  source case identity. The adapter never elevates self-declared same-agent
  configuration or E0 result to independently qualified evidence.
- Use explicit, preselected rate limits to give a diagnostic `within_limits`
  answer only when denominators are large enough. No fitting on the evaluation
  cohort and no automatic tuning of production thresholds.
- Return aggregate counts/rates only. Original case IDs, queries, gold,
  native source bytes, tool schemas, secrets and observed model text are not
  serialized. Source authorship, permission, license and gold are self-attested
  and all external/E2 qualification flags remain false.

## Rejected alternatives

1. Feed the existing generic confidence calibrator `no_route` as unsupported:
   would collapse missing native proof into false global absence.
2. Build independent publisher gold or certify signed-off review in code:
   impossible from local structural bytes and violates the E2 hold.
3. Re-run a model from the scorer: would permit test leakage and another agent
   path; offline observed status is the only evaluation input.

## Proof obligations

Positive: exact source-bound EN/KO/JA full five-class cohort, correct
per-language denominators, supported refusal vs unsupported acceptance,
deferred not incorrectly counted as immediate error, and bounded aggregate
output. Negative: missing/duplicate/foreign outcomes, arbitrary/forged
statuses, altered source bytes, false `verified` flags and raw source leakage.
CI should exercise the evaluator with synthetic source streams but must
explicitly keep the resulting report unqualified.

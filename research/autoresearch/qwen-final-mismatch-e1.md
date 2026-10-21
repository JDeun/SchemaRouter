# Qwen3 final-answer strict verification failure diagnosis — exposed E1

Issue [#1583](https://github.com/JDeun/SchemaRouter/issues/1583).

Actual pinned model and original Open-Meteo source run
[39180663648](https://github.com/JDeun/SchemaRouter/actions/runs/39180663648)
found that the original `state_ready` agent completed both validated
real provider calls for KO and JA but **both** failed the final exact
source-observed JSON check, while the experimental progress notice
did not rescue any of the three tasks. We are not changing its
0/3, the prior run's 1/3 or any strict task oracle.

The existing boolean `_matches_weather_final` remains the **sole
correctness evaluator**; a separate host-owned and source-observed
failure classifier describes only the first coarse observed discrepancy:
- `invalid_json`: malformed/duplicate-key/invalid numeric constant
- `invalid_shape`: wrong object structure or missing/extra keys
- `invalid_types`: wrong primitive types
- `temperature_mismatch`: valid numeric field differs from original
  executed weather source
- `unit_mismatch`: original source unit disagreement
- `timestamp_mismatch`: original source observation timestamp differs
- `multiple_source_fields`: at least two independent source fields differ.

The classifier returns `None` only when the original strict oracle
also succeeds. Tests assert identical strict outcomes and no values,
observed timestamps, coordinates, model text, source replies, URLs or
credentials appear in telemetry. Real Qwen3 + original Open-Meteo E1
re-executes both unchanged `all_visible` and `state_ready` arms
under a symmetric, separately approved original GET retry budget of 1.
A source HTTP failure remains a source failure, not a final-format
error. Results are bounded to publisher-exposed EN/KO/JA samples.

**E1 diagnostic only**, not held-out source-author task data, not
independent model improvement and not production metadata exposure
beyond opt-in trusted research. Native public API/default agent,
original #432 negative and v0.18 #1356 HOLD remain unchanged;
#1346 publisher-owned gold / #1477 actual held-out paired E2 remain
unsatisfied.

# SafeAct V1 independent-contract preflight

These files provide **unscored** research mechanisms, not a completed
SafeActBench evaluation. The upstream revision is
`841816cf1e376e6fbf8600cffac5df1736e1d369`; its V1 set contains 131 cases.

Independently approve a contract using only agent-visible/public capabilities
and policies. Never use hidden evaluator requirements, labels or trajectories.
Every source reference should declare an allowed `kind`, a relative `path`,
and the exact lowercase SHA-256 digest of the frozen *actual public file*.

To verify source identity from a trusted parent process, run:

```bash
python scripts/verify_safeact_v1_sources.py contracts.json --source-root public-sources/
```

This verifies path safety, file identity and post-freeze tampering. It **does not
establish independent authorship or semantic correctness**.

For a parent-process session, use
`TrustedEvidenceSession.from_verified_sources(..., source_root=trusted_path)`
to fail closed on the pinned source files **before** any tool invocation.
The trusted parent supplies `source_root`; never accept it from model output.
The ordinary constructor is mechanism-test only and does not attest source files.

`TrustedEvidenceSession` wraps agent-inaccessible information/action callers
and verifies real tool results before adding observations. It records per-case
mechanism diagnostics, not official task success or unsupported execution.
For post-run comparison only, validate three official `external_agent`
output directories with `python scripts/verify_safeact_v1_comparison.py`
and the required `--safeact-ungated`,
`--safeact-schemarouter-no-evidence-gate`, and
`--safeact-schemarouter-evidence-gate` directory options.
This checks 131 paired case fingerprints, actual runtime-model attestation,
ephemeral sessions and per-case official artifact SHA-256 values. It reports
only the official strict task-success metric; unsupported executions,
premature attempts and false refusals are **not yet scored here**.

The full independently approved contracts, official agent bridge and scored
131-case three-condition evaluation remain pending.

## Official three-arm runtime integrity preflight

Before any scored claims, use `validate_comparison_matrix()` on exactly
three `V1RunPlan` objects. The official runner is invoked by absolute path.
After official trajectories finish, call `audit_v1_completions(plans)` from a
trusted parent process. The audit reads only post-run completion markers and
checks that all 131 public case IDs match across conditions, that the
requested and observed model identities match the frozen model, and that
each task used a fresh ephemeral session. It rejects symlinked markers.

This is a **post-run runtime identity check, not a SafeAct score**. Hidden
evaluator contents, gold labels, and evaluation records are not read or
exposed to the agent. Official evaluator scores remain a separate output.

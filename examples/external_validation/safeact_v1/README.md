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

`TrustedEvidenceSession` wraps agent-inaccessible information/action callers
and verifies real tool results before adding observations. It records per-case
mechanism diagnostics, not official task success or unsupported execution.
The full independently approved contracts, official agent bridge and scored
131-case three-condition evaluation remain pending.

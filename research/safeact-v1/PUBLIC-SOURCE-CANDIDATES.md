# SafeActBench public policy source snapshot — unreviewed

Eight public template policy files have been copied **byte-for-byte** from
[SafeActBench](https://github.com/caoshidong66/safeact), pinned to revision
`841816cf1e376e6fbf8600cffac5df1736e1d369`. Original benchmark/environment data are CC BY 4.0; retain
this attribution with any distributed copies.

This material is an **unreviewed candidate source archive**, not an independently
authored or approved Evidence Contract. It does not specify the target action for
any of the 131 V1 case IDs, establish evidence requirements, validate a model,
authorize a scored run, or satisfy the independent human reviewer checkpoint.
The `ops_code_agent` domain has no corresponding public template policy
directory, which is not evidence that its actions require no authorization.

No evaluator, hidden gold, case manifests, or materialized evidence were used
to build these candidate snapshots. Run the byte-integrity checker after
fetching the pinned upstream source:

```bash
python -m scripts.verify_safeact_v1_public_snapshot \
  --manifest research/safeact-v1/public-policy-source-candidates.json \
  --source-root research/safeact-v1/public-sources \
  --upstream-root safeact-upstream
```

The checker compares the SHA-1 Git blob identity of each file with its pinned
upstream counterpart and prints a SHA-256 digest for contract authorship.
It rejects unexpected files, symlinks, missing policy sources and case/gold paths.
Any human-authored contract must separately record and verify exact source
SHA-256, independently justified action/field semantics, and reviewer approval.

Tracking: #1211, #1224, #1268. No official scored model evaluations completed.

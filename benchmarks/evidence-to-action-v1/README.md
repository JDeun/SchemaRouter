# Evidence-to-Action v1

This directory is the deterministic regression harness for issue 1203. It is not presented as an external benchmark result.

Run:

```bash
python scripts/run_evidence_to_action_ablation.py \
  --cases benchmarks/evidence-to-action-v1/cases.json \
  --json-out artifacts/evidence-to-action-v1.json
```

The seed corpus deliberately contains supported and unsupported consequential actions. The routing-only conditions execute every selected action; the evidence-gated condition applies the frozen trusted-local evidence contract before action.

The checked-in `baseline-results.json` is the expected deterministic seed result. Any future external-agent or SafeActBench-derived evaluation must be reported separately with model, prompt, tool environment, dataset version, repetitions, and confidence intervals.

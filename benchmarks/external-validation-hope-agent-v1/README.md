# hope-agent × SchemaRouter frozen offline package

This directory is the decision package requested in `shiwenwen/hope-agent#802`.

It is intentionally **pure retrieval only**: no tool execution, no external I/O, no paid model call, and no credential is required. The full catalog remains eligible; the comparison does not reinterpret preselection as removal of capabilities.

## Frozen revisions

- SchemaRouter source: `060a9accdea5be7601e274be8987c98160253fa9`
- hope-agent reference: `2784abba5823922dba06a3c722eba0ca91f69fd6`
- both repositories: MIT

The catalog/field annotations are a frozen subset of the pre-existing SchemaRouter 0.14 synthetic capability catalog in `benchmarks/agent_utility_v5_catalog.py`. The package contains 12 tools and 16 queries: 10 supported, 3 unsupported, and 3 ambiguous negatives.

## Required outputs

For every case, return:

- compact `candidate_tools`;
- actually `activated_tools`;
- exact `exposed_schemas` that become model-visible;
- `cold_start_ms`;
- `hot_path_ms`.

The scorer computes candidate recall, activation recall, required-field recall, unsupported/ambiguous false activation, actual schema bytes, budget compliance, and latency summaries.

## Commands

```bash
python scripts/external_validation_hope_agent.py validate \
  --package-dir benchmarks/external-validation-hope-agent-v1

python scripts/external_validation_hope_agent.py template \
  --package-dir benchmarks/external-validation-hope-agent-v1 \
  --out /tmp/hope-agent-result.json

python scripts/external_validation_hope_agent.py score \
  --package-dir benchmarks/external-validation-hope-agent-v1 \
  --results /tmp/hope-agent-result.json
```

The runner uses only the Python standard library.

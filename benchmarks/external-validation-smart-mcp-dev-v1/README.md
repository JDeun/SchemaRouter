# SchemaRouter × SmartMCP cross-project benchmark — development fixture v1

This package implements the **development/smoke phase** discussed in:

- SchemaRouter: https://github.com/JDeun/SchemaRouter/issues/1114
- SmartMCP: https://github.com/spak2005/smart-mcp/issues/4

It is deliberately **not held-out evidence**. The catalog and cases are visible so both maintainers can review the protocol, naming, task strata, Top-K values, exposure accounting, and runner behavior before anything is frozen.

## What is compared

The planned primary comparison keeps the catalog, queries, Top-K values, and scoring procedure fixed while preserving each implementation's native retrieval behavior:

1. SmartMCP semantic discovery;
2. SchemaRouter typed field-aware retrieval;
3. a simple lexical/raw-spec baseline.

This development package contains 21 tools and 33 cases covering exact retrieval, sibling operations, input constraints, output semantics, read/write/destructive siblings, multi-tool coverage, multilingual/mixed-identifier requests, ambiguity, near-OOD, and OOD.

## Files

- `catalog.json`: canonical shared capability catalog, including typed output/policy metadata.
- `smartmcp-snapshot.json`: the same tools projected into SmartMCP's existing offline snapshot format (`name`, `description`, `inputSchema`).
- `cases.json`: shared development queries and gold required-tool sets.
- `manifest.json`: current protocol and pinned source revisions.
- `result-template.json`: implementation-neutral result contract.

## Validate and score

```bash
python scripts/external_validation_smart_mcp.py validate \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1

python scripts/external_validation_smart_mcp.py template \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --out /tmp/smartmcp-cross-result.json

python scripts/external_validation_smart_mcp.py score \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --results /tmp/smartmcp-cross-result.json
```

The scorer uses only the Python standard library.

### Latency measurement boundary

Hot-path latency is measured after one unmeasured per-query warmup. For every
condition, the timed region includes both ranked candidate retrieval and
construction of the model-visible per-candidate contract. JSON encoding and tool
execution are excluded. This keeps SmartMCP, SchemaRouter, and the lexical
baseline on the same observable boundary.

`index_build_ms` measures condition-specific catalog/index construction after
runtime imports. For SmartMCP, embedding-model object initialization is outside
that timer; only embedding/index construction over the shared catalog is timed.

## Execution provenance

Fixture authorship and execution provenance are intentionally separate. The
`source_revisions` values in `manifest.json` describe the revisions used when
the visible development fixture was authored; runners do **not** reuse those
values as if they were the code that actually executed a later run.

Each runner records:
- the actual git revision when it can be detected from the executed source;
- `commit_source` (`git`, `explicit`, or `unavailable`);
- the fixture reference revision for comparison;
- the installed package version when applicable.

When a runner executes from an installed wheel rather than a git checkout, pass
`--implementation-revision <exact-sha-or-release-revision>`. A future held-out
package must provide an actual implementation revision; the shared scorer rejects
publishable held-out results that omit it.

## Run SmartMCP without modifying SmartMCP core

Install the pinned-compatible SmartMCP package/environment, then run:

```bash
python scripts/run_smartmcp_external_validation.py \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --implementation-revision c4d6602cfabb6f514bf06a1d1ae10b610ff7d573 \
  --out /tmp/smartmcp-dev-result.json

python scripts/external_validation_smart_mcp.py score \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --results /tmp/smartmcp-dev-result.json
```

The adapter imports SmartMCP's public embedding index and reproduces its native search behavior over the frozen offline snapshot. It does not execute upstream tools and does not modify SmartMCP.

## Run SchemaRouter typed retrieval

SchemaRouter is evaluated through its public side-effect-free `SchemaRouter.retrieve` API. The adapter registers the shared typed catalog as `ToolSpec` / `EndpointSpec` contracts and serializes the returned `CapabilityCandidate` objects exactly as exposed to downstream selection.

```bash
python scripts/run_schemarouter_external_validation.py \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --out /tmp/schemarouter-dev-result.json

python scripts/external_validation_smart_mcp.py score \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --results /tmp/schemarouter-dev-result.json
```

Execution remains disabled; the runner performs retrieval only.

## Run the raw-spec lexical baseline

The baseline uses deterministic TF-IDF cosine ranking over the same surface SmartMCP embeds: tool name, description, and top-level input parameter names/descriptions.

```bash
python scripts/run_lexical_external_validation.py \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --out /tmp/lexical-dev-result.json

python scripts/external_validation_smart_mcp.py score \
  --package-dir benchmarks/external-validation-smart-mcp-dev-v1 \
  --results /tmp/lexical-dev-result.json
```

It has no abstention threshold; it always returns a deterministic ranked Top-K, so unsupported-query behavior is reported rather than hidden.

## Fairness boundary

- The full catalog remains eligible for every query.
- No external tool execution is performed.
- No paid LLM is required.
- SmartMCP sees the same `name`, `description`, and `inputSchema` data it normally embeds.
- SchemaRouter may use its typed metadata because testing the utility of that representation is the point of the comparison.
- Schema exposure is measured from the exact capability/search contracts actually made model-visible, not from the size of the source catalog.
- Development results may be used to fix harness bugs or agree on protocol details.
- Development results must **not** be reported as held-out validation.
- Held-out cases must be generated/frozen only after both sides agree on the protocol.

## Next freeze decision

Before a real comparison, both maintainers should explicitly agree on at least:

- catalog construction/provenance;
- query-generation and held-out separation;
- Top-K values;
- model/version for SmartMCP embeddings;
- SchemaRouter retrieval configuration;
- lexical baseline definition;
- latency machine/runtime;
- exposure serialization;
- treatment of unsupported/ambiguous cases;
- publication of raw results, including negative results.

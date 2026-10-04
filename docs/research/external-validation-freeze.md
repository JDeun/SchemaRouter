# Frozen external validation package

Use this contract when an external project asks for an inspectable evaluation package before
agreeing to a cross-project benchmark.

The package is intentionally framework-neutral. It freezes provenance and evaluation authority;
it does not make SchemaRouter authoritative for the upstream project's execution.

## Required artifacts

Before scoring, freeze:

1. exact SchemaRouter and upstream commit SHAs;
2. the catalog used by both systems, its SHA-256 digest, source, and license;
3. the source and digest of field-contract labels;
4. supported, unsupported, and ambiguous cases plus frozen tool/field ground truth;
5. the same Top-K and schema-disclosure budget;
6. cold and hot latency definitions, warmup count, and measured-run count;
7. whether candidate recall and activation recall are distinct for the upstream system.

Start from `benchmarks/external-validation-freeze-manifest.template.json`. Change
`status` to `frozen` only after every required artifact exists and its digest has been recorded.

Validate before the first scoring run:

```bash
python scripts/validate_external_validation_freeze.py path/to/frozen-manifest.json
```

The validator fails closed if provenance, labels, budgets, field recall, unsupported rejection,
offline execution boundaries, or freeze governance are incomplete.

## Metric semantics

**Tool recall** and **field recall** are separate. A system that retrieves the correct tool but
cannot identify output fields can report tool recall while field recall is marked from the same
frozen field labels; do not silently impute fields from SchemaRouter metadata.

**Candidate recall** and **activation recall** are also separate when the upstream system has a
two-stage discovery/activation design.

**Exposed schema bytes** means canonical UTF-8 bytes actually disclosed to the downstream agent or
model under the frozen budget. Source-code byte counts may be reported separately but must not be
mixed with wire/schema bytes.

**Unsupported rejection** measures cases for which no catalog capability satisfies the request.
**Ambiguous abstention** measures intentionally under-specified cases whose frozen label requires
abstention or clarification.

## Latency

Cold and hot measurements must be declared before scoring. A typical offline definition is:

- cold: first process invocation including index/model/catalog initialization;
- hot: retrieval after a fixed number of untimed warmups in the same process.

Report environment/hardware separately when results are published. Do not compare GPU HYSET
latency directly with CPU SchemaRouter latency without retaining the hardware label.

## Current external queues

- HYSET (#795): upstream commit `93808cb8d633b6b685f0f9353923b27c2ad7ad81`; upstream source is MIT, while `data/hyset_corpus.json` remains subject to ToolBench terms. Use a compatible released ToolBench subset and do not redistribute data beyond its license.
- pi-jev (#796): upstream commit `c5b5847aa189fe5ffec52893b7051fe8f9e7a548`; MIT. Freeze a small shared catalog first and report Jev tool activation separately from SchemaRouter field narrowing.
- hope-agent (#799): upstream commit `2784abba5823922dba06a3c722eba0ca91f69fd6`; MIT. The upstream maintainer explicitly requested this frozen decision package before deciding whether to participate.

These commit SHAs are discovery anchors, not permanent benchmark pins. A comparison manifest must
pin the exact commit actually used when the case/catalog artifacts are frozen.

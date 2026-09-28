# Operation-routing freeze protocol

SchemaRouter freezes a routing candidate before it can enter independent confirmation, calibration,
or blind evaluation.

The purpose of the freeze is to make the evaluated system a reproducible object rather than a moving
research configuration.

## When to freeze

Freeze only after a candidate passes every canonical development target:

- supported exact-route accuracy >= 85%;
- near-domain unsupported rejection >= 97%;
- OOD rejection = 100%;
- false-route rate <= 1%;
- authority violations = 0;
- execution errors = 0;
- target combined p95 <= 250 ms.

A quality pass with a latency miss may enter a separately preregistered runtime-only optimization,
but semantic behavior must remain unchanged.

## What the freeze must contain

Start from:

`benchmarks/operation-routing-freeze-manifest.template.json`

Copy the template to a candidate-specific JSON file. Use status `frozen-dev` after the DEV candidate
is frozen and `fresh-confirmed` only after the independent fresh confirmation passes.

Record the exact:

- SchemaRouter source revision;
- architecture identifier;
- route-authority and verifier/veto roles;
- model, checkpoint, provider, and runtime revisions;
- Python/dependency/hardware identity;
- query/capability/prompt representation digests;
- option ordering rule;
- decision rule and threshold;
- development corpus/workflow/artifact provenance;
- development metrics;
- independent fresh-confirmation corpus/workflow/artifact provenance;
- fresh-confirmation metrics.

Validate a DEV freeze before confirmation:

```bash
python scripts/validate_operation_routing_freeze_manifest.py \
  benchmarks/<candidate-freeze>.json \
  --phase dev
```

After the independent fresh confirmation is recorded, change the status to `fresh-confirmed` and
validate again with `--phase fresh`. The validator fails on missing provenance, target drift,
authority drift, invalid digests, or evidence that misses the standing gate.

The manifest also records the authority invariants:

- only finite locally registered IDs may be selected;
- no rank-2 fallthrough after a winner is rejected;
- no pseudo-route;
- an external model cannot create execution authority.

## Confirmation boundary

A development pass is not enough.

After freezing the exact candidate, generate a **new zero-overlap fresh confirmation surface** that is
distinct from the failed #270 and #287 surfaces. Run the frozen candidate once without semantic
retuning.

Failed confirmation corpora are permanently confirmation-only. They must never be reused to:

- choose a threshold;
- change a prompt;
- add aliases;
- create route/language/family exceptions;
- select a model;
- train or calibrate a verifier.

Only a candidate that survives this independent confirmation may enter #198.

## Calibration and blind-final

#198 owns the final evidence sequence:

1. freeze;
2. independent fresh confirmation;
3. new 900-case calibration corpus;
4. one calibration evaluation;
5. only after a calibration pass, generate a new 1,800-case blind-final corpus;
6. evaluate blind-final exactly once.

Calibration and blind evidence become consumed after use and cannot be recycled into tuning.

## Runtime-only optimization

If quality passes but latency fails, runtime optimization may change implementation details such as
quantization or execution backend only when the exact semantic decision function is preserved.

The optimized runtime needs its own recorded identity and confirmation before calibration.

## Evidence recording

For every terminal phase, preserve:

- source SHA;
- corpus seed/hash;
- workflow run ID;
- artifact ID and digest;
- exact model/runtime identity;
- aggregate and required slice metrics;
- authority/error counts;
- terminal decision and interpretation.

Update #200, #197, the research ledger, design/experiment history, and #199 whenever the frozen
candidate or evidence phase changes.

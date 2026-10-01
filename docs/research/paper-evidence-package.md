# Research evidence package

SchemaRouter keeps the research record in
`benchmarks/research-experiment-ledger.json`. The ledger is the source of truth; paper
tables are derived views and must not become an independent source of experimental facts.

## Generate

```bash
python scripts/export_research_evidence.py
```

The default output directory is `docs/research/generated/` and contains:

- `research-evidence-package.json` — machine-readable aggregate with targets,
  governance, current conclusion, flattened experiments, and invalidated runs.
- `research-experiments.csv` — table-ready experiment/provenance/metric rows.
- `invalidated-runs.csv` — invalid or pre-result technical runs that must not be cited as
  model-quality evidence.
- `research-evidence-table.md` — compact human-readable experiment table.

Generated files are build artifacts rather than a replacement for the canonical ledger. CI
runs the exporter so schema drift is caught before paper preparation.

## Evidence roles

The exporter preserves the ledger's evidence-role distinctions. In particular, tuning DEV,
fresh confirmation, calibration, blind-final, design-known stress, compatibility, and
infrastructure evidence must not be collapsed into one accuracy table without their role.

A development pass is not a generalization claim. A fresh-confirmation failure is consumed
negative evidence and is not eligible for threshold repair. Calibration and blind-final
remain blocked until the exact frozen candidate has passed a new zero-overlap fresh
confirmation under the repository freeze protocol.

## Provenance requirements

A result is paper-ready only when the available record identifies the experiment, source
revision, workflow run, artifact and digest, corpus identity/role, frozen configuration,
metrics, and terminal decision. Missing historical fields are represented as missing values;
the exporter never invents provenance.

The invalidated-run table exists so contract failures, cancelled pre-result runs, leakage
incidents, and other non-evidence executions remain visible instead of disappearing from the
narrative.

## Architecture interpretation

SchemaRouter separates execution authority from semantic evidence:

```text
user request
    |
registered schema + local authority
    |
bounded ranking / evidence / veto
    |
accept registered route OR abstain
    |
local validation / policy / execution
```

A semantic model may rank, veto, or abstain over finite registered authority according to the
preregistered experiment. It does not create a new executable tool, endpoint, field, argument,
or pseudo-route.

## Threats to validity

The evidence package should be read with these limits:

- benchmark corpora are synthetic controlled workloads and cannot by themselves establish
  production prevalence or user-distribution performance;
- multilingual template coverage is broader than English-only testing but is not equivalent
  to natural traffic from each language community;
- GitHub-hosted CPU latency is reproducible infrastructure evidence, not a universal hardware
  benchmark;
- repeated architecture search on canonical DEV increases selection pressure, which is why
  zero-overlap fresh confirmation and one-shot calibration/blind evidence are kept separate;
- registry descriptions and trusted aliases are part of the tested system and may differ in
  quality across real integrations;
- provider/model compatibility is not evidence of routing quality;
- aggregate metrics can hide route/language/family collapse, so promotable candidates must
  retain slice diagnostics and authority/error counts.

## Final-paper closure

The package can be regenerated throughout the active 0.14 cycle, but final paper tables must not
treat an active or infrastructure-invalid run as scientific evidence. The current closure path is:

- terminal #431 corrective aggregate and preregistered gate;
- terminal #432 large held-out generalization result;
- terminal #424 final-answer factual/value/unit/provenance result;
- terminal #510 runtime qualification and the successor projection result if that field-level line
  is included in the paper.

Historical calibration/blind work from the earlier operation-routing lineage remains part of the
ledger, but it is not a substitute for the frozen 0.14 held-out and final-answer evidence above.
Every final table must be reconstructable from the canonical ledger plus immutable workflow/artifact
provenance without semantic retuning from consumed or invalid runs.

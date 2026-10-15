# Current-main typed retrieval: multilingual DEV diagnostic (#1412)

**Status:** previously exposed, deterministic synthetic development benchmark
only. Source checkout is recorded in each report; frozen 0.14 independent
historical results are neither regenerated nor used to tune candidate
selection. This is a diagnostic for the **current** product's public
\`SchemaPlanner.retrieve()\`, **not** a new independent test.

## Why this second development gate exists

The first current-main [baseline](current-main-baseline.md) runs synthetic
20/50/100/250/500 catalog break-even cells and Gearlynx E1. All 15 cells
yielded 100% Top-3 recall on their exposed development gold, so they are
insufficient to locate important language/set-coverage failures. This next
gate reuses the already-existing \`benchmarks/agent_utility_v5_catalog.py\`
asset without changing it:

- 100/250/500 registered **synthetic typed** capability catalogs, each
  with 30 shared core endpoints and catalog-size-specific distractors;
- English/Korean/Spanish/Japanese/German/mixed input; English-heavy
  registration metadata, no implicit translation authority;
- eight balanced strata: clear single-tool, sibling-operation ambiguity,
  adjacent distractors, multi-step first-hop, typed numeric units, read/write
  siblings, near-domain unsupported and OOD;
- 240 existing query/task rows per catalog (48 in default balanced smoke).
  The historical gold contains **required route sets only**, not
  verified required output-field sets or final agent task completions.

The runner calls the current \`SchemaPlanner.retrieve(PlanRequest(...), k=10)\`
once per task, then evaluates Top-3/5/10 slices of the **same** ranked
candidate list. This is an economical ranking-equivalent extraction, but
timings at K3 and K5 are **measured K10 latency**, not independently timed
K3/K5. The exact candidate JSON bytes are a payload-size proxy: they are
not schema-only bytes, tokenizer-exact token counts or FULL agent context.

## Correct outcome semantics

1. **Required-route recall** is micro-averaged across supported multi-route
   tasks, counting each required registered endpoint.
2. **All-required FullCoverage@K** is the fraction of supported tasks with
   every necessary endpoint present in the selected shortlist. It is *not*
   Top-1 exact tool choice or end-to-end agent task success.
3. **Unsupported nonempty shortlist rate** is the fraction of unsupported
   tasks receiving candidates. It is not unauthorized execution, calibrated
   no-match effectiveness or a false-tool-call rate.
4. Selected serialized JSON bytes indicate payload cost, not proven prompt
   compression benefit.
5. Per-language and per-stratum results are reported separately; average
   scores must never hide KO/JA failures. Every miss retains task ID and
   missing route IDs for diagnostics.

Neither the scorer nor candidate list grants tool execution. The runner
does **not** instantiate native vector/graph/record provider clients, apply
\`PrincipalContext\` policy, execute endpoints, make model calls, evaluate
final answers or use immutable blinded confirmation. Thus it cannot
establish end-to-end v0.18 correctness, security qualification or production
readiness. The \`ToolSpec\` schemas are representative synthetic typed
objects, **not verified live heterogeneous-provider schemas**.

## Reproduce at a fixed source checkout

\`\`\`bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_current_main_multilingual_dev.py

# Balanced 48-task/size smoke: 144 retrievals plus 3 Top-K scored slices
python -m scripts.research_current_main_multilingual_dev \
    --sizes 100 250 500 --cases-per-group 1 \
    --output artifacts/current-main-multilingual-dev/report.json

# Full old visible DEV, 240 cases per catalog:
python -m scripts.research_current_main_multilingual_dev \
    --sizes 100 250 500 --cases-per-group 5 \
    --output artifacts/current-main-multilingual-dev/full-report.json
\`\`\`

The workflow's pull request path runs only the balanced low-cost smoke to
protect shared GitHub Actions Linux runners while v0.18 release qualification
continues. The manual workflow input can run all 240/size. Each report
includes the checked-out Git SHA, file digests, stable case-list digest,
all case-level misses and cohort summaries.

## Next actual AutoResearch prerequisite

Freeze a **genuinely fresh** query-disjoint *training and new DEV* suite
from representative **real heterogeneous current-adapter** OpenAPI/MCP/
database/vector/graph providers, with separately supplied trusted principal
allow sets, required output-field gold, multi-tool dependencies and an
unseen independent final check. Do not generate that from #432/#424 or
call pre-exposed #430 rows new. Only then add an editable research-only
retriever/field-selection strategy, isolated unprivileged code-edit agent
and actual FULL/SR-K/SR-PROGRESSIVE/ORACLE agent evaluation.

The release gate (#1345/#1346) remains authoritative; success here may not
auto-merge model changes, authorize tools, or publish v0.18.

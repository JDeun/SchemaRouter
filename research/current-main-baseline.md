# Current-main performance baseline and AutoResearch audit

**Research checkpoint:** 2026-10-16 · Parent [#1412](https://github.com/JDeun/SchemaRouter/issues/1412) · baseline starting source `main@0bc91d5284cf013aeb7cb09b9fdd3e9b6e9b69e9`.

> This document is a code-and-benchmark asset map. It does not certify product
> performance. Run the accompanying benchmark on the **exact** checked-out
> commit and read the generated `baseline.json` and two raw reports before
> stating any measured current-main result. Numbers from an old frozen 0.14
> research pipeline are not a measurement of the live 0.17/main library.

## Canonical product shape: not merely 0.14 and not an autonomous agent

The current public library is a **typed capability routing and governed
execution boundary** between host agents/apps and heterogeneous provider
systems. It provides retrieval *and* optional bounded selection, planning,
validated execution and typed output projection. Hosts own conversations,
high-level task intent, authority sources, model-provider decisions and agent
loops. Runtime authorization and binding/schema validation stay mandatory
before any invocation. An optional decision backend cannot invent an
endpoint, authorized scope, parameter or execution grant.

| Current area | Current-code entrypoints and provenance | Optimization boundary |
| --- | --- | --- |
| Ingestion and provider resolution | `runtime.py`, `provider_registration.py`, `provider_profiles.py`, `adapters/`, `native_registration.py` | Preserve source identity and contract fidelity across heterogeneous OpenAPI/MCP/OPTIMADE/SDK, relational, vector, graph and record providers |
| Registry and typed contracts | `registry.py`, `models.py`, `capability_contracts.py`, `capability_snapshot.py`, `capability_graph.py` | Preserve endpoint, parameter, field, semantic/unit and schema-fingerprint identities, snapshot concurrency |
| Retrieval and field-first planning | `planner.py`, `planning_context.py`, `planning_stages.py`, `embedding_e5.py` | Optimize eligible set recall, required-field coverage, multilingual representation and schema exposure, not just top-1/9-label operation classification |
| Progressive/state-aware retrieval | `state_retrieval.py`, `execution_state.py`, `adaptive_context.py` | Optimize bounded refresh/coverage only on host-permitted typed state; no oracle task graphs or hidden gold |
| Optional bounded decision and no-fit | `decisions.py`, `decision_policy.py`, `operation_fit.py`, `retrieval_abstention.py`, `retrieval_execution_gate.py` | Ranking/no-fit is advisory or opt-in; declared operation-fit comes from host, not a learned classifier |
| Authorization, execution, evidence | `authorization.py`, `authorization_config.py`, `executor.py`, `policy.py`, `validation.py`, `trace_redaction.py` | Never relax principal/RBAC/ABAC/data scope, schema/argument checks, destructive guard, output fidelity and privacy |
| Agent-facing adapters | `integrations/`, `adapters/`, `runtime.py` | Measure actual agent task success without moving conversation/orchestration into SchemaRouter |

## Existing reusable research surfaces (not interchangeable)

| Asset | What it legitimately measures | What it **cannot** claim |
| --- | --- | --- |
| `scripts/benchmark_realistic_break_even.py` | 15 synthetic size (20/50/100/250/500) × sibling-ambiguity cells; simple lexical vs schema lexical vs exhaustive/current indexed route retrieval; supported route recall, nonempty unsupported shortlists, contract bytes, retrieval latency | Heterogeneous real provider coverage, actual unauthorized calls, calibrated no-match, agent pass, independent multilingual validation |
| `scripts/benchmark_retrieval_hot_path.py` | Pinned public Gearlynx E1 development fixture, indexed vs legacy result identity, lightweight route refs vs full typed candidate materialization and latency | Independent agent utility, production traffic or cross-machine latency equivalence |
| `scripts/evaluate_multilingual_embedding_cpu_dev.py` / `evaluate_multilingual_embedding_scale_dev.py` | Previously exposed real MiniLM/E5/BGE/Qwen CPU retrieval studies; synthetically expanded 100/250/500 *English-only* schema descriptions | Fresh multilingual independent confirmation, real multilingual provider aliases, 500 real endpoints |
| `scripts/evaluate_agent_utility_v5_structural_retrieval.py`, `benchmarks/agent_utility_v5_catalog.py` | Existing visible six-language, synthetic 240-task structural DEV benchmark and 100/250/500 nested catalogs | New disjoint test, actual fresh real-provider generalization |
| `scripts/evaluate_agent_utility_v3_heldout.py`, `evaluate_agent_utility_v3_heldout_retrieval.py` | Frozen 0.14 historical independent evaluation | Retuning, regeneration or a current-main score |
| `scripts/evaluate_operation_intent_cpu_dev.py` and `research_operation_fit_auto_loop.py` | Previously seen 72-case auxiliary operation-hypothesis DEV | Primary current product's typed capability retrieval/field/agent quality |
| `tests/test_capability_retrieval.py`, `test_capability_negotiation.py`, `test_state_retrieval_integration_fixtures.py`, `test_retrieval_execution_gate.py` | Concrete current typed, principal and plan integrity regressions | Independent statistical task success |

## First executable baseline: strictly scoped

The new `scripts/research_current_main_baseline.py` invokes **only**
the two already registered offline development benchmarks and validates their
entire expected comparison/semantic-drift shapes. It writes:

- `realistic-break-even.json` — complete 15-cell, four-arm DEV retrieval matrix;
- `gearlynx-hot-path.json` — source-level identity and request timing evidence;
- `baseline.json` — checked-out Git commit, SHA-256 of benchmark/catalog/current runtime code,
  compact size/ambiguity results, Gearlynx timings, and explicit `unmeasured_requirements`.

Run after installing the package on an isolated Linux CPU runner:

```bash
python -m pip install . "pytest>=8,<10"
python -m pytest -q tests/test_research_current_main_baseline.py
python scripts/research_current_main_baseline.py \
  --iterations 1 --output-dir artifacts/current-main-baseline
```

**Interpretation caution:** A top-3 nonempty shortlist on a synthetic
unsupported query is *not* an unauthorized execution or a failed agent answer.
The historical script calls this `false_route_rate`; our summary explicitly
renames it `unsupported_nonempty_shortlist_rate`. The baseline also compares
two forms of the existing SchemaRouter implementation: `schemarouter_full`
means **exhaustive in-library scoring without a candidate index**, not the
FULL all-tool-schema *agent* comparison arm. Neither runner calls an LLM.

A single iteration is only an inexpensive correctness/smoke baseline: p95
numbers should not be used for statistical superiority claims. Run repeated,
paired CPU measurements later with hardware and source pinned. Do not compare
absolute times across hosts.

## Required next stage before AutoResearch-generated code is useful

1. Freeze a **new development cohort** covering current product contracts:
   genuine heterogenous provider schemas, authorized principal/data scopes,
   read/write siblings, multilingual EN/KO/JA + ES/DE/mixed identifiers,
   semantic fields/units, multi-hop route sets and unsupported/OOD prompts.
   Pair task clusters across catalog sizes; reserve genuinely separate
   independently authored confirmation. Never mine #432/#424 gold rows.
2. Expose an experimental, easily editable **retrieval/field/progressive
   strategy adapter** behind the current public API, with immutable host
   authorization/contract/execution layers and protected evaluator. Require
   case-level FullCoverage@K, field recall, initial vs eventual exposure,
   schema-token/byte cost, p95/RAM and policy invariants.
3. Implement an unprivileged self-editing agent loop:
   hypothesis → permitted code-only changes → real CPU benchmark →
   multi-objective KEEP/DISCARD/CRASH with full diff/source/metric lineage →
   persistent next hypothesis. No arbitrary code in a privileged workflow,
   auto-merges, execution grants, secret-bearing runners or product cutover.
4. Compare frozen research champions using the **same actual agent** across
   FULL / SR-K / SR-PROGRESSIVE / ORACLE. Record authorization and validated
   tool/field/task outcomes. Reserve #1346/#1345 release gates: v0.18.0 remains
   HOLD until its prior independent prerequisites are satisfied.

**Status:** First PR provides a reproducible *development baseline* and
architecture audit, **not** a working AutoResearch code-edit agent, a new
external validation or a production-quality outcome. The separate unmerged
`research/1412-autoresearch-execution-v1` branch has an obsolete operation
classifier prototype; do not integrate it.

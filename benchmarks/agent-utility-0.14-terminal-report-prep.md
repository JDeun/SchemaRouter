# Research 0.14 — terminal evidence report preparation

> Preparation only (2026-10-10). **Not a terminal research result.** Do not publish this file as a completed paper table or derive a claim from unfinished shard rows.
>
> Authority: `benchmarks/research-experiment-ledger.json`, frozen preregistrations and *terminal canonical* workflow artifacts, not this template. All placeholders below intentionally remain unscored.

## Frozen research question and comparison

Does typed bounded capability retrieval preserve end-to-end agent utility, factual answers and execution safety while reducing model-visible tool schema/context compared with FULL?

- Core strong-agent model: `HuggingFaceTB/SmolLM3-3B`, revision `a07cc9a04f16550a088caea529712d1d335b0ac1`.
- Frozen downstream science source: `30663de8f618bc88a893d9bf6214035a70e8e894`.
- Frozen comparison controls: FULL, fixed SR-5, fixed SR-10, SR-PROGRESSIVE, ORACLE. Optional structural K3 and state-aware corrective conditions must only be present when their preregistered upstream gates passed; they were **not** promoted for the current held-out dispatch.
- Never interpret failed/unfinished infrastructure runs as measured model-quality negatives. Never tune selection width, model, prompts, score threshold, scorer, corpora, exclusions or inference strategy after frozen outcome visibility.

## Confirmed context, not fresh held-out generalization

| Evidence | Status | Defensible observation | Limit |
| --- | --- | --- | --- |
| Phase A / B1, #418 / #420 | terminal | B1 SR-5 task pass 91.30% vs FULL 68.48%; tool-schema exposure 5.42% of FULL; 0 unauthorized destructive executions | Controlled repeated 23-task mechanism surface, not population generalization |
| Canonical strong-agent B2 #423 | terminal run `36642658406` | Exact 460-episode strong-agent replication completed | Do not transplant small-model B1 figures to B2 |
| Structural fixed K3 promotion | terminal negative | No optional K3 promotion into held-out | Negative ablation retained |
| #431 corrective promotion | terminal gate resolved | No state-aware promotion into held-out | Keep candidate-specific evidence independent |
| #506 output-field projection DEV | terminal run `36682589574` | 1,152-episode diagnostic produced no interpretable answer-quality comparator because agent mostly skipped tool calls | Not projection confirmation; do not report zeros as equivalence |

## Primary end-stage provenance (fill only after canonical success)

| Required field | #432 large held-out | #424 final answer |
| --- | --- | --- |
| Issue | [#432](https://github.com/JDeun/SchemaRouter/issues/432) | [#424](https://github.com/JDeun/SchemaRouter/issues/424) |
| Status | **ACTIVE — no canonical aggregate yet** | **NOT YET DISPATCHED** |
| Canonical run ID | Pending (current candidate `38012340016`) | Pending |
| Exact source SHA | `30663de8f618bc88a893d9bf6214035a70e8e894` | Verify from run input |
| Corpus task count | 780 independent semantic tasks | 144 independent answer-bearing tasks |
| Catalog sizes | 100 / 250 / 500 downstream; retrieval includes 1000 | 100 / 250 |
| Matrix | 234 evaluation shards | 72 evaluation shards |
| Canonical artifact ID / name | Pending | Pending |
| Canonical artifact SHA-256 digest | Pending | Pending |
| Corpus/content SHA-256 | Pending; use validated artifact | Pending; use validated artifact |
| Model/runtime/checkpoint proof | Pending shard aggregation | Pending shard aggregation |
| Completeness / identity validation | Pending 234/234 + aggregate | Pending 72/72 + aggregate |
| Preregistered primary gate | Pending | Pending |
| Invalid/pre-result attempts | Record separately; see #500 | Record separately |
| Provenance-verified disposition | **Do not assert yet** | **Do not assert yet** |

## Analysis tables — no row values until accepted aggregates

### #432 paired task utility and retrieval exposure

| Condition | Paired task pass | Delta vs FULL (percentage points) | Task-clustered 95% CI | Required-tool recall | Schema tokens vs FULL | Unauthorized destructive executions |
| --- | --- | --- | --- | --- | --- | --- |
| FULL | Pending | Reference | N/A | Pending | 100% reference | Pending |
| SR-5 | Pending | Pending | Pending | Pending | Pending | Pending |
| SR-10 | Pending | Pending | Pending | Pending | Pending | Pending |
| SR-PROGRESSIVE | Pending | Pending | Pending | Pending | Pending | Pending |
| ORACLE (diagnostic bound) | Pending | Pending | Pending | Pending | Pending | Pending |

- Paired estimand: per semantic task, average over catalog repeats; bootstrap on **780 task clusters**, never treat 780×3 catalog rows as independent.
- Report language (EN/KO/ES/JA/DE/mixed), catalog-size, task-family and safety slices, including negative/zero changes.
- The nominal -2 percentage point criterion is an engineering margin unless the preregistered 95% paired interval actually establishes it. Sample size does not guarantee a narrow 2pp interval in advance.
- Separate model inference/selection wall latency, input/output token use, schema token reduction and any cost assumptions.

### #424 deterministic final-answer quality

| Condition | Required fact recall | Value/numeric correctness | Unit correctness | Provenance correctness | Unsupported/contradictory facts | Total input tokens |
| --- | --- | --- | --- | --- | --- | --- |
| FULL | Pending | Pending | Pending | Pending | Pending | Pending |
| SR-5 | Pending | Pending | Pending | Pending | Pending | Pending |
| SR-10 | Pending | Pending | Pending | Pending | Pending | Pending |
| SR-PROGRESSIVE | Pending | Pending | Pending | Pending | Pending | Pending |
| ORACLE | Pending | Pending | Pending | Pending | Pending | Pending |

Report non-inferiority, false facts, tool/evidence coverage and total/schema input-token constraints **separately**. A high benchmark task-pass score is not evidence of correctly grounded final answers.

## Outcome and paper claim decision matrix

| Verified result | Permitted paper statement | Disallowed inference |
| --- | --- | --- |
| Held-out broad-claim gate passes, with valid confidence intervals and safety | Scoped generalization to the frozen synthetic multilingual task/catalog population | Production prevalence; universal model/provider advantage |
| Held-out gate fails or cannot establish 2pp non-inferiority | Negative/uncertain generalization outcome; keep prior controlled mechanism result | Reuse or tune the consumed held-out set |
| Final-answer gate passes | Scoped factual-answer preservation on the 144-task answer surface | Assume all external agents/evidence sources have same fidelity |
| Final-answer gate fails | Preserve negative outcome and failure taxonomy | Replace scorer or cherry-pick post-result tasks |
| Infra/provenance validation fails | No scientific result; repair transport/workflow only and preserve identity | Interpret incomplete row subsets as model evidence |

## Terminal acceptance checklist

- [ ] Canonical run IDs all terminal and green; no duplicate competing run adopted.
- [ ] Artifact ZIPs, names, SHA-256s, frozen source and **all** required shard IDs verified.
- [ ] #432 corpus independence, 780 semantic-task identities, repeated-measure clustering, confidence intervals and safety checked.
- [ ] #424 fresh 144-task corpus disjointness, exact evidence/facts/units/provenance scorer checked.
- [ ] Conditional promotion gates recorded exactly from preregistration; negative ablations reported unchanged.
- [ ] Raw metrics and slice tables imported **from canonical artifacts only**; invalid technical runs excluded but retained.
- [ ] Machine-readable experiment ledger updated by explicit provenance-verified change, then `python scripts/export_research_evidence.py` rerun.
- [ ] #500 terminal digest and issue #417 children reconciled; #199 draft revised with appropriate research limitations.
- [ ] Separate #506/#510 output-field projection not silently conflated with the core 0.14 held-out answer-quality result.
- [ ] README, English/Korean docs, slides and external outreach use only approved claim boundaries.

## Operational recovery rules (infrastructure only)

- Conveyor: `.github/workflows/research-0.14-conveyor.yml` runs on stage completions and the hourly recovery scan.
- Before an evaluation matrix exists, workflow-wrapper failures may need a new pinned-source dispatch to obtain a fixed wrapper.
- Once held-out/final evaluator jobs exist, retry only failed jobs **of that same workflow run**, bounded by `MAX_INFRA_ATTEMPTS=3`; preserve completed shards and original frozen experiment inputs.
- If retries exhaust, **stop and report**; do not loop indefinitely or mislabel an execution exception as a scientific negative.
- GitHub Actions' `queued` status does not imply zero scientific work: inspect job counts and active matrix jobs.
- Final authoritative measurements require successfully aggregated, digest-checked artifacts, regardless of whether the controller or underlying Action job appeared green.

This template is intentionally an interpretive/operational checklist: it **does not** edit the original preregistration, ledger, scientific source or consumed corpus.

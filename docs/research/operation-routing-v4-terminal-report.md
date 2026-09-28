# Operation routing v4 terminal report

Cycle: `0.11-operation-routing-quality-v4`  
Decision date: **2026-09-28**  
Status: **closed without a promoted production-target candidate**

## Decision

The 0.11 architecture-search cycle is complete. It does **not** claim that SchemaRouter has
validated the standing 85/97/100/1 + 250 ms production target under independent request-surface
shift.

The strongest executable development candidate passed every canonical DEV gate, but the exact frozen
candidate failed a new zero-overlap fresh confirmation. Calibration and blind-final were therefore
not consumed.

## Standing target

| Metric | Target |
| --- | ---: |
| Supported exact route | >= 85% |
| Near-domain unsupported rejection | >= 97% |
| OOD rejection | 100% |
| False-route rate | <= 1% |
| Authority / execution errors | 0 |
| Executable p95 | <= 250 ms |

Canonical DEV: 1,800 rows, SHA
`fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

## Strongest DEV candidate and decisive fresh result

| Evidence | Exact | Near reject | OOD | False-route | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| #324/#325 executable DEV | **85.07%** | **99.31%** | **100%** | **0.62%** | **176.94 ms** |
| #326/#327 frozen fresh | **84.81%** | **90.45%** | **100%** | **8.49%** | **278.37 ms** |

The fresh run is the promotion decision. It failed both the supported-exact floor, the near-domain
rejection floor, the false-route ceiling, and the p95 target. The fresh corpus is permanently
confirmation-only and may not become tuning data.

## What was ruled out

The cycle tested multiple structurally distinct families rather than repeatedly tuning one threshold:

- positive dense score/margin boundaries and winner-first gating;
- operation-fit selectors and hierarchical ranking variants;
- multilingual NLI;
- explicit negative capability prototypes, signed banks, dual negative/background banks, and
  rank-based prototype rules;
- grouped-OOF learned verifier geometry followed by fit-once fresh confirmation;
- BGE reranker / cross-encoder veto and rescue variants;
- Qwen, Laya, Kev and AnyJev typed-decision paths;
- lightweight BGE negative veto + conditional GTE rescue;
- BGE-M3 native ColBERT/sparse operation evidence;
- registry-self-calibrated endpoint alias envelopes;
- threshold-free BGE/GTE top-1 consensus.

The final three post-fresh experiments were deliberately derived from canonical tuning DEV and
trusted registry/model invariants only. None used #270/#287/#326 rows for repair.

## Final technical finding

BGE-M3 raw registered-route top-1 reaches about **88.45%**, so closed-set route ranking is not the
dominant late-stage blocker.

The unresolved problem is **capability membership under open-set surface shift**:

> When a request is topically close to a registered domain but asks for an unregistered operation,
> semantic rankers can still select a plausible registered endpoint with high confidence.

This explains why stronger ranking, model agreement, alias contrast, and several learned or
prototype-based gates can look good on development data yet fail to preserve unsupported rejection
on an independent request surface.

## Safe reference profile

The #259 robust BGE-M3 profile remains the most useful conservative reference:

- supported exact: **83.77%**;
- near-domain rejection: **98.96%**;
- false-route: **0.93%**;
- planner p95: **~134.95 ms**.

It is **not** renamed or promoted as a production-target profile because it misses the 85% supported
exact requirement.

## Why calibration and blind-final were not run

Issue #198 requires a candidate that:

1. passes canonical DEV;
2. is frozen exactly;
3. passes a new zero-overlap fresh confirmation;
4. validates as `fresh-confirmed`.

No 0.11 candidate satisfied those entry requirements. Running calibration or blind-final anyway
would consume evidence without a valid promoted candidate and would weaken the research protocol.

## Successor-cycle boundary

A later cycle should begin only with a **materially new source of capability evidence**, not another
post-hoc threshold on the same score geometry.

It must not:

- train or tune from #270, #287, or #326;
- revive a terminal 0.11 family with route/language/family exceptions;
- add rank-2 fallback or a pseudo-route to rescue rejected winners;
- treat provider compatibility as routing-quality evidence.

Any successor must preregister its architecture, data role, model/runtime identity, authority
semantics, stopping rule, and fresh-confirmation protocol before behavior-changing evaluation.

## Reproducibility

Machine-readable closure:
`benchmarks/operation-routing-v4-terminal-decision.json`

Canonical evidence ledger:
`benchmarks/research-experiment-ledger.json`

Full design and experiment history:
`docs/research/design-and-experiment-history.md`

Paper-ready exports:
`python scripts/export_research_evidence.py`

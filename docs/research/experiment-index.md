# Complete experiment index

This page exposes the **full experiment ledger** for SchemaRouter's routing research rather than only
the latest or strongest results.

The public summary page intentionally answers “where the research currently stands.” This page
answers a different question: **what was actually tried?**

Current machine-readable ledger:

- independent experiment records: **84**;
- legacy routing corpus lineage: **13** versioned corpora;
- routine bugfix-only commits are not counted as independent experiments unless they changed an
  architecture invariant, evaluation protocol, or empirical claim;
- failed, superseded, invalidated, and terminal experiments are retained rather than hidden.

The 84-record count includes the terminal 0.13 V6A–V6H/open-set controls and the active 0.14 agent-utility lineage. Terminal 0.13 confirmation surfaces remain unopened unless explicitly recorded otherwise.

The canonical machine-readable source is
[`benchmarks/research-experiment-ledger.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json).
The narrative source is
[Design and experiment history](design-and-experiment-history.md).

For **what to try next and why**, use the
[Prior-art roadmap](prior-art-roadmap.md) and active GitHub issue **#417**. Historical 0.13 prior-art mapping remains in **#388**. Those surfaces map literature
to canonical work items and record active/next/backlog/deferred state so a new session does not
recreate terminal experiments.

## How to read the evidence

A Git commit is not the same thing as an experiment. One squashed PR may contain implementation,
tests, preregistration, corpus freeze, calibration, and final evidence; conversely, one experiment
may require several commits or workflow runs. The ledger therefore treats the **experimental
decision** as the unit of record and links it back to issues, PRs, revisions, workflows, artifacts,
and source files when available.

The repository Git history remains the exhaustive engineering record.

## Legacy corpus lineage

| Corpus | Role |
| --- | --- |
| [`decision-routing-v1.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v1.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v2.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v2.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v3.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v3.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v4-operation-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v4-operation-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v5-operation-calibration.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v5-operation-calibration.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v6-operation-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v6-operation-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v7-operation-post-change-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v7-operation-post-change-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v8-operation-alias-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v8-operation-alias-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v9-operation-alias-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v9-operation-alias-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v10-operation-generalization-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v10-operation-generalization-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v11-operation-generalization-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v11-operation-generalization-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v12-operation-contrastive-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v12-operation-contrastive-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |
| [`decision-routing-v13-operation-contrastive-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v13-operation-contrastive-holdout.json) | Earlier routing / holdout lineage retained in Git history and later research governance |

## Legacy / pre-cycle

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `pre-0.8-no-route-sentinel-ablation` | **sentinel_removed** | An explicit none_of_the_above pseudo-option could improve empty-recall no-route discrimination. | [issue #87](https://github.com/JDeun/SchemaRouter/issues/87) · [`e41f57a044`](https://github.com/JDeun/SchemaRouter/commit/e41f57a044182deb374980c28d66863d637a691b) |

## 0.10-operation-contrastive-v1

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-contrastive-bge-v1` | **blind_final_passed_for_optional_profile** | Sibling-contrastive BGE operation-fit can improve supported operation routing while retaining near-domain unsupported rejection. | ledger / Git history |

## 0.10-operation-cascade-v2

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-cheap-first-cascade-v2` | **rejected_on_calibration** | A MiniLM fast-path plus selective BGE reranking can reduce CPU latency while preserving preregistered quality floors. | ledger / Git history |

## 0.10-operation-graph-projection-v3

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-graph-projection-v3` | **rejected_on_fresh_calibration** | A typed schema graph can own routing authority while semantic signals provide bounded soft evidence, reducing latency without sacrificing quality/safety. | [PR #181](https://github.com/JDeun/SchemaRouter/pull/181) |

## 0.11-operation-routing-quality-v4

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.11-v4-fresh-baseline` | **baseline_only** | Fresh natural-language development data can expose the post-0.10 routing bottleneck without reusing consumed calibration/blind evidence. | [PR #187](https://github.com/JDeun/SchemaRouter/pull/187) |
| 2 | `0.11-hierarchical-tool-operation` | **rejected_on_development** | Separating tool-domain selection from within-tool operation selection will improve exact-route accuracy while preserving rejection. | [PR #189](https://github.com/JDeun/SchemaRouter/pull/189) |
| 3 | `0.11-accepted-operation-selector` | **standalone_candidate_rejected_primitive_retained** | If operation-fit already identifies a registered route, allowing that accepted route to control the single-call candidate will recover endpoint accuracy without changing the abste… | [PR #190](https://github.com/JDeun/SchemaRouter/pull/190) |
| 4 | `0.11-stage-signal-diagnostics` | **diagnostic_supports_multi_signal_boundary_design** | Candidate-fit score geometry can reveal which supported misses are recoverable and whether a global similarity threshold can separate supported from near-domain unsupported reques… | [`1cf7efc261`](https://github.com/JDeun/SchemaRouter/commit/1cf7efc261b5bcb16b50a8794c8abbf84ed9265c) |
| 5 | `0.11-typed-evidence-infrastructure` | **infrastructure_retained_for_next_candidate** | Recorded design / evaluation step. | ledger / Git history |
| 6 | `0.11-route-local-threshold-ablation` | **rejected_on_development** | Per-route pairwise minimum-score thresholds can recover open-set safety while preserving the operation-narrow supported-routing gain. | [PR #191](https://github.com/JDeun/SchemaRouter/pull/191) |
| 7 | `0.11-nli-boundary-superseded` | **superseded_before_result_interpretation** | Recorded design / evaluation step. | [PR #192](https://github.com/JDeun/SchemaRouter/pull/192) |
| 8 | `0.11-pairwise-tool-hierarchy` | **rejected_on_development** | Pairwise tool ranking crossed the 70% supported gate but did not provide an open-set capability boundary and badly missed rejection/false-route gates. | [PR #193](https://github.com/JDeun/SchemaRouter/pull/193) |
| 9 | `0.11-direct-multilingual-nli-boundary` | **rejected_on_development** | Conservative entailment thresholds improved unsupported rejection but collapsed supported recall; direct NLI is unsuitable as the operation selector/gate tested here. | [PR #194](https://github.com/JDeun/SchemaRouter/pull/194) |
| 10 | `0.11-bounded-retrieve-rerank-architecture` | **architecture_implemented_diagnostic_pending** | Recorded design / evaluation step. | [PR #195](https://github.com/JDeun/SchemaRouter/pull/195) · [`90af3e1fce`](https://github.com/JDeun/SchemaRouter/commit/90af3e1fce3bf29f45fd3347c14afc2603b37d5e) |
| 11 | `0.11-bounded-rerank-score-diagnostic` | **ranking_headroom_validated_latency_optimization_required** | Recorded design / evaluation step. | [PR #205](https://github.com/JDeun/SchemaRouter/pull/205) · [`f43535b6ef`](https://github.com/JDeun/SchemaRouter/commit/f43535b6ef0acbc5492b9791e6757e28a343d9fa) |
| 12 | `0.11-winner-only-threshold-semantics` | **mechanism_merged_into_active_research_stack** | Recorded design / evaluation step. | [PR #208](https://github.com/JDeun/SchemaRouter/pull/208) |
| 13 | `0.11-evidence-projector-active-stack` | **infrastructure_merged_into_active_research_stack** | Recorded design / evaluation step. | ledger / Git history |
| 14 | `0.11-bounded-rerank-width-ablation` | **selected_width_2_by_preregistered_smallest_passing_width_rule** | Recorded design / evaluation step. | [PR #216](https://github.com/JDeun/SchemaRouter/pull/216) · [`9f4dbff423`](https://github.com/JDeun/SchemaRouter/commit/9f4dbff423cdcb9151d00d1b15586f9b3d766235) |
| 15 | `0.11-joint-score-margin-boundary` | **not_selected** | Joint score+margin gating adds only ~0.35 percentage points at the same false-route budget, insufficient to justify a larger route-local tuning surface before width/latency optimi… | ledger / Git history |
| 16 | `0.11-width2-winner-gate-executable` | **rejected_on_development_latency_gate** | A width-2 bounded semantic recall plus score-only BGE rank-then-gate boundary can satisfy the 0.11 development quality gates without material latency regression. | [PR #228](https://github.com/JDeun/SchemaRouter/pull/228) · [`fdaf3f77e9`](https://github.com/JDeun/SchemaRouter/commit/fdaf3f77e95b504e81739c69cd1d9889d36afabb) |
| 17 | `0.11-cheap-action-only-evidence-diagnostic` | **retain_as_cheap_bounded_selector_or_auxiliary_evidence_not_global_direct_fast_path** | A cheap multilingual embedding over endpoint action names and trusted operation aliases can provide independent routing evidence at materially lower latency than BGE. | [PR #230](https://github.com/JDeun/SchemaRouter/pull/230) · [`521dcc65e0`](https://github.com/JDeun/SchemaRouter/commit/521dcc65e0269d68c76a372606f8d22b2ac57aa1) |
| 18 | `0.11-action-guided-single-pair-bge-diagnostic` | **rejected_on_supported_recall** | Use cheap action-only evidence to choose one already-authorized width-2 candidate, then score only one BGE pair to remove CPU tail latency. | [issue #231](https://github.com/JDeun/SchemaRouter/issues/231) · [PR #232](https://github.com/JDeun/SchemaRouter/pull/232) |
| 19 | `0.11-bounded-action-embedding-diagnostic` | **rejected_on_open_set_supported_recall** | Replace BGE inside width-2 authorized recall with cached action-only MiniLM embedding evidence. | [issue #233](https://github.com/JDeun/SchemaRouter/issues/233) · [PR #236](https://github.com/JDeun/SchemaRouter/pull/236) |
| 20 | `0.11-minilm-dual-view-diagnostic` | **rejected_backbone_capacity_insufficient** | Use one MiniLM query embedding against cached schema/domain and action-only route views to separate ranking evidence from open-set confidence. | [issue #240](https://github.com/JDeun/SchemaRouter/issues/240) · [PR #241](https://github.com/JDeun/SchemaRouter/pull/241) |
| 21 | `0.11-multilingual-embedding-backbone-screen` | **bge_m3_selected_for_strict_open_set_optimization** | Keep the dual-view routing architecture fixed and change only multilingual embedding backbone capacity. | [issue #242](https://github.com/JDeun/SchemaRouter/issues/242) · [PR #243](https://github.com/JDeun/SchemaRouter/pull/243) |
| 22 | `0.11-gte-winner-bge-rejector` | **rejected_on_supported_recall** | Let high-capacity GTE choose one winner and use one BGE cross-encoder pair only as the unsupported-operation rejector. | [issue #244](https://github.com/JDeun/SchemaRouter/issues/244) · [PR #249](https://github.com/JDeun/SchemaRouter/pull/249) |
| 23 | `0.11-bge-m3-budget6-executable-confirmation` | **not_promoted_literal_freeze_missed_by_one_case** | One supported papers.citations case scored ~1.35e-7 below its frozen threshold; all planner/direct parity and safety gates passed, but the literal 960-correct frozen projection re… | [issue #245](https://github.com/JDeun/SchemaRouter/issues/245) · [PR #247](https://github.com/JDeun/SchemaRouter/pull/247) |
| 24 | `0.11-bge-m3-fine-fusion-strict` | **no_fusion_weight_reached_85_percent_strict_target** | Best preregistered strict point was 83.77% exact at 98.96% near-domain rejection and 0.93% false-route. No interpolation or out-of-grid retuning was permitted. | [issue #246](https://github.com/JDeun/SchemaRouter/issues/246) · [PR #248](https://github.com/JDeun/SchemaRouter/pull/248) · [`9d6f5bdc18`](https://github.com/JDeun/SchemaRouter/commit/9d6f5bdc18c933a35d4f8f9983c12c850ab9b0fb) |
| 25 | `0.11-conditional-zero-false-rejected-winner-rescue` | **rejected_zero_false_rescue_recovers_only_5_of_required_15** | Recorded design / evaluation step. | [issue #255](https://github.com/JDeun/SchemaRouter/issues/255) · [PR #258](https://github.com/JDeun/SchemaRouter/pull/258) |
| 26 | `0.11-route-local-stable-bge-m3-fusion` | **rejected_strict_boundary_below_85_percent_despite_90_54_raw_ceiling** | Route-local fusion weights selected from the already-preregistered #246 grid may recover the remaining exact-route gap while midpoint/canonicalized thresholds remove observed-scor… | [issue #256](https://github.com/JDeun/SchemaRouter/issues/256) · [PR #257](https://github.com/JDeun/SchemaRouter/pull/257) |
| 27 | `0.11-numerically-robust-threshold-freeze-policy` | **required_for_future_frozen_candidates** | Recorded design / evaluation step. | [issue #253](https://github.com/JDeun/SchemaRouter/issues/253) |
| 28 | `0.11-bge-m3-robust-budget6-executable-confirmation` | **confirmed_as_numerically_robust_strict_base_for_conditional_rescue** | Recorded design / evaluation step. | [issue #259](https://github.com/JDeun/SchemaRouter/issues/259) · [`9e9b1049ea`](https://github.com/JDeun/SchemaRouter/commit/9e9b1049eac779adbc5781bfc45a447966ae32e8) |
| 29 | `0.11-cross-model-zero-false-abstention-rescue` | **gte_agreement_bge_selected_for_frozen_confirmation** | Recorded design / evaluation step. | [issue #262](https://github.com/JDeun/SchemaRouter/issues/262) · [PR #263](https://github.com/JDeun/SchemaRouter/pull/263) |
| 30 | `0.11-zero-false-cross-model-frozen-candidate` | **rejected_surface_fragile_positive_open_set_boundary** | Recorded design / evaluation step. | [issue #265](https://github.com/JDeun/SchemaRouter/issues/265) · [PR #270](https://github.com/JDeun/SchemaRouter/pull/270) |
| 31 | `0.11-robust-base-winner-crossencoder-rescue` | **rejected_safe_but_insufficient_rescue** | Recorded design / evaluation step. | [issue #266](https://github.com/JDeun/SchemaRouter/issues/266) |
| 32 | `0.11-native-bge-m3-abstention-geometry-rescue` | **rejected_native_geometry_insufficient** | Recorded design / evaluation step. | [issue #271](https://github.com/JDeun/SchemaRouter/issues/271) |
| 33 | `0.11-typed-contradiction-only-nli-veto` | **rejected_generic_nli_neutral_on_supported_and_unsupported** | Recorded design / evaluation step. | [issue #273](https://github.com/JDeun/SchemaRouter/issues/273) |
| 34 | `0.11-explicit-negative-capability-prototype-veto` | **rejected_combined_winner_domain_ood_veto** | Recorded design / evaluation step. | [issue #275](https://github.com/JDeun/SchemaRouter/issues/275) · [PR #276](https://github.com/JDeun/SchemaRouter/pull/276) |
| 35 | `0.11-global-signed-capability-prototype-bank` | **rejected_global_signed_prototype_evidence_too_coarse** | Recorded design / evaluation step. | [issue #277](https://github.com/JDeun/SchemaRouter/issues/277) · [PR #278](https://github.com/JDeun/SchemaRouter/pull/278) |
| 36 | `0.11-dual-signed-negative-openworld` | **rejected_scalar_signed_evidence_overlap** | Recorded design / evaluation step. | [issue #279](https://github.com/JDeun/SchemaRouter/issues/279) · [PR #280](https://github.com/JDeun/SchemaRouter/pull/280) |
| 37 | `0.11-rank-based-capability-set-openworld` | **rejected_fixed_prototype_heuristics_terminated** | Recorded design / evaluation step. | [issue #281](https://github.com/JDeun/SchemaRouter/issues/281) · [PR #283](https://github.com/JDeun/SchemaRouter/pull/283) · [`944df2e0f2`](https://github.com/JDeun/SchemaRouter/commit/944df2e0f2dc8617e7b97e6a38d4e2f5684f5324) |
| 38 | `0.11-grouped-oof-learned-winner-verifier` | **promote_hgb_p0_500_to_separate_frozen_candidate** | Recorded design / evaluation step. | [issue #285](https://github.com/JDeun/SchemaRouter/issues/285) · [PR #286](https://github.com/JDeun/SchemaRouter/pull/286) · [`cfaafb84bb`](https://github.com/JDeun/SchemaRouter/commit/cfaafb84bb651a6d6d38c4ce741f05ac61f37e9e) |
| 39 | `0.11-external-qwen3-semantic-capability-verifier` | **reject** | Recorded design / evaluation step. | [issue #289](https://github.com/JDeun/SchemaRouter/issues/289) · [PR #290](https://github.com/JDeun/SchemaRouter/pull/290) · [`68e812ab5c`](https://github.com/JDeun/SchemaRouter/commit/68e812ab5c72bd42664e21f8c9f62a760465cb03) |
| 40 | `0.11-frozen-hgb-winner-verifier-candidate` | **rejected_fresh_surface_generalization_failure** | Recorded design / evaluation step. | [issue #287](https://github.com/JDeun/SchemaRouter/issues/287) · [PR #288](https://github.com/JDeun/SchemaRouter/pull/288) · [`e5b10ee01e`](https://github.com/JDeun/SchemaRouter/commit/e5b10ee01ec23af6113c562b51e1db0c6d003d7a) |
| 41 | `0.11-system-one-provider-contract` | **accepted_reusable_infrastructure** | Recorded design / evaluation step. | [issue #291](https://github.com/JDeun/SchemaRouter/issues/291) · [PR #292](https://github.com/JDeun/SchemaRouter/pull/292) · [`7f4118ea05`](https://github.com/JDeun/SchemaRouter/commit/7f4118ea059ab448ca132a3ef83b7a43135318c8) |
| 42 | `0.11-pluggable-system-one-routing` | **direct_laya_rejected_parent_remains_open_for_system_one_comparison** | Recorded design / evaluation step. | [issue #293](https://github.com/JDeun/SchemaRouter/issues/293) · [PR #294](https://github.com/JDeun/SchemaRouter/pull/294) · [`48e329ee94`](https://github.com/JDeun/SchemaRouter/commit/48e329ee949d0d7a42d93a7c06c7ecbc62edfedc) |
| 43 | `0.11-kev-08b-choice-noul-screen` | **no_quality_result_runtime_nonviable** | Recorded design / evaluation step. | [issue #299](https://github.com/JDeun/SchemaRouter/issues/299) · [PR #300](https://github.com/JDeun/SchemaRouter/pull/300) |
| 44 | `0.11-pinned-laya-noul-veto` | **reject** | Recorded design / evaluation step. | [issue #301](https://github.com/JDeun/SchemaRouter/issues/301) · [PR #302](https://github.com/JDeun/SchemaRouter/pull/302) · [`46af3c3d01`](https://github.com/JDeun/SchemaRouter/commit/46af3c3d0156b7b7bfd40686aa5639571f91a936) |
| 45 | `0.11-laya-choice-noul-full-catalog` | **superseded_by_301** | Recorded design / evaluation step. | [issue #295](https://github.com/JDeun/SchemaRouter/issues/295) · [PR #296](https://github.com/JDeun/SchemaRouter/pull/296) |
| 46 | `0.11-top4-typed-capability-routing` | **same_laya_variant_dominated; provider_neutral_contingency_only** | Recorded design / evaluation step. | [issue #303](https://github.com/JDeun/SchemaRouter/issues/303) · [PR #310](https://github.com/JDeun/SchemaRouter/pull/310) |
| 47 | `0.11-generic-decision-callable-benchmark` | **accepted_reusable_infrastructure** | Recorded design / evaluation step. | [issue #304](https://github.com/JDeun/SchemaRouter/issues/304) · [PR #305](https://github.com/JDeun/SchemaRouter/pull/305) · [`c9678b95a6`](https://github.com/JDeun/SchemaRouter/commit/c9678b95a6dc592a1c3b850a6aea8b1675ff94a4) |
| 48 | `0.11-anyjev-l0-content-free-noul-veto` | **await_realistic_runtime_before_execution** | Recorded design / evaluation step. | [issue #311](https://github.com/JDeun/SchemaRouter/issues/311) · [PR #313](https://github.com/JDeun/SchemaRouter/pull/313) |
| 49 | `0.11-bge-plus-kev-global-noul` | **source_kev_analysis_missing** | Recorded design / evaluation step. | [issue #314](https://github.com/JDeun/SchemaRouter/issues/314) |
| 50 | `0.11-lightweight-negative-gte-offline-compose` | **pass_promote_executable** | Recorded design / evaluation step. | [issue #322](https://github.com/JDeun/SchemaRouter/issues/322) · [PR #323](https://github.com/JDeun/SchemaRouter/pull/323) |
| 51 | `0.11-lightweight-negative-gte-executable` | **pass_dev_promote_fresh** | Recorded design / evaluation step. | [issue #324](https://github.com/JDeun/SchemaRouter/issues/324) · [PR #325](https://github.com/JDeun/SchemaRouter/pull/325) |
| 52 | `0.11-lightweight-bge-gte-frozen-fresh-confirmation` | **reject_after_fresh_failure** | Recorded design / evaluation step. | [issue #326](https://github.com/JDeun/SchemaRouter/issues/326) · [PR #327](https://github.com/JDeun/SchemaRouter/pull/327) · [`b19d7b0255`](https://github.com/JDeun/SchemaRouter/commit/b19d7b0255ee9717464b6fa65ce1ebdeaf58a1bd) |
| 53 | `0.11-bge-m3-colbert-operation-contract` | **reject** | Recorded design / evaluation step. | [issue #328](https://github.com/JDeun/SchemaRouter/issues/328) · [PR #329](https://github.com/JDeun/SchemaRouter/pull/329) · [`4c72f2dd19`](https://github.com/JDeun/SchemaRouter/commit/4c72f2dd1939edb6ecf8415d620dbb5d58683fa0) |
| 54 | `0.11-bge-registry-alias-envelope` | **reject** | Registry-derived sibling contrast preserves recall but accepts unsupported requests; registry cohesion rejects unsupported requests only by collapsing supported exact to ~24% and … | [issue #332](https://github.com/JDeun/SchemaRouter/issues/332) · [PR #333](https://github.com/JDeun/SchemaRouter/pull/333) · [`fa091f4329`](https://github.com/JDeun/SchemaRouter/commit/fa091f43296eb1ca680f39921010482275bb4cda) |
| 55 | `0.11-bge-gte-threshold-free-consensus` | **reject** | Cross-backbone top-1 agreement behaves as route-selection confidence rather than unsupported-capability evidence: two strong rankers frequently agree on the same plausible registe… | [issue #336](https://github.com/JDeun/SchemaRouter/issues/336) · [PR #337](https://github.com/JDeun/SchemaRouter/pull/337) · [`d25f427569`](https://github.com/JDeun/SchemaRouter/commit/d25f427569fc4419a72963c6f31994fa170805f6) |
| 56 | `0.11-registry-compiled-capability-verifier` | **terminal_rejected_overconservative_veto** | A provider-neutral capability IR plus generic synthetic counterfactual supervision can veto unsupported operations for arbitrary newly registered native/OpenAPI/MCP tools without … | [issue #338](https://github.com/JDeun/SchemaRouter/issues/338) · [PR #341](https://github.com/JDeun/SchemaRouter/pull/341) · [`ef75100abc`](https://github.com/JDeun/SchemaRouter/commit/ef75100abc1bb03a80ef2d7cfbd9d463accfb623) |

## 0.12-query-first-typed-capability

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-query-first-typed-frame-v1` | **terminal_rejected_insufficient_open_set_rejection** | A registry-independent explicit request frame plus deterministic within-tool contract filtering can turn same-domain unsupported operations into empty capability sets without lear… | [issue #347](https://github.com/JDeun/SchemaRouter/issues/347) · [PR #348](https://github.com/JDeun/SchemaRouter/pull/348) · [`ef0e0a567f`](https://github.com/JDeun/SchemaRouter/commit/ef0e0a567f12129bf9f4b003d13f9f6e9679a216) |

## 0.12-semantic-action-ontology

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-semantic-action-ontology-v1` | **terminal_rejected_flat_semantic_argmax** | A frozen registry-independent multilingual semantic action ontology can classify request operation semantics before deterministic tool-local capability matching without learned th… | [issue #349](https://github.com/JDeun/SchemaRouter/issues/349) · [PR #352](https://github.com/JDeun/SchemaRouter/pull/352) · [`38ee755756`](https://github.com/JDeun/SchemaRouter/commit/38ee7557565983746e33741897e6168bf4f35643) |

## 0.12-hierarchical-capability-ontology

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-hierarchical-capability-ontology-v1` | **terminal_rejected_hard_ontology_filter** | A hierarchical executable-capability ontology with root/leaf constraints and contrastive multilingual prototypes can improve open-set membership while preserving registered execut… | [issue #354](https://github.com/JDeun/SchemaRouter/issues/354) · [PR #357](https://github.com/JDeun/SchemaRouter/pull/357) · [`250845bba0`](https://github.com/JDeun/SchemaRouter/commit/250845bba058a704ab50cdde43326cc1e5c26d62) |

## 0.12-asymmetric-ontology-veto

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-asymmetric-ontology-veto-v1` | **terminal_rejected_high_precision_low_recall_asymmetric_veto** | Preserve the frozen BGE-M3 raw top-1 as the sole positive route selector and use ontology evidence only as an asymmetric unsupported-membership veto under a fixed independent-agre… | [issue #358](https://github.com/JDeun/SchemaRouter/issues/358) · [PR #360](https://github.com/JDeun/SchemaRouter/pull/360) · [`759359882c`](https://github.com/JDeun/SchemaRouter/commit/759359882c3deb1be310fc540bbb1780b1543885) |

## 0.12-capability-set-membership-veto

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-capability-set-membership-consensus-v1` | **terminal_rejected_membership_consensus_insufficient** | Replace exact unsupported-leaf agreement with anchored-tool capability-set membership consensus while preserving frozen BGE-M3 as the sole positive route selector. | [issue #363](https://github.com/JDeun/SchemaRouter/issues/363) · [PR #364](https://github.com/JDeun/SchemaRouter/pull/364) · [`f198f896c4`](https://github.com/JDeun/SchemaRouter/commit/f198f896c44860c27ce14b4c88200096ef0b754f) |

## 0.12-external-zeroshot-membership

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-external-multilingual-zeroshot-membership-v1` | **terminal_rejected_multiclass_outside_label_no_open_set_boundary** | A small externally pretrained multilingual zero-shot classifier can judge whether a request belongs to the finite capability set registered for the BGE-anchored tool, while remain… | [issue #371](https://github.com/JDeun/SchemaRouter/issues/371) · [PR #372](https://github.com/JDeun/SchemaRouter/pull/372) · [`5e6dde0c38`](https://github.com/JDeun/SchemaRouter/commit/5e6dde0c3860ff46f0961c74233d7196e6c86f59) |

## 0.12-set-conditioned-binary-entailment

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-set-conditioned-binary-entailment-v1` | **terminal_rejected_all_not_entailment** | Use one direct NLI sequence-pair judgment over the anchored tool's full registered capability set; preserve the frozen BGE-M3 winner on entailment and veto to NO_ROUTE on not-enta… | [issue #374](https://github.com/JDeun/SchemaRouter/issues/374) · [PR #375](https://github.com/JDeun/SchemaRouter/pull/375) · [`e61058d0aa`](https://github.com/JDeun/SchemaRouter/commit/e61058d0aa31819bf99b182f4bd5947dd0d11fab) |

## 0.12-independent-capability-entailment

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-independent-per-capability-entailment-v1` | **terminal_rejected_independent_entailment_over_veto** | Judge every registered capability leaf independently with a pinned multilingual NLI model; preserve frozen BGE-M3 raw top-1 if any registered leaf is entailed, otherwise veto to N… | [issue #377](https://github.com/JDeun/SchemaRouter/issues/377) · [PR #379](https://github.com/JDeun/SchemaRouter/pull/379) · [`a872c9602d`](https://github.com/JDeun/SchemaRouter/commit/a872c9602dcad959ea1bf10f16a052592754d4ae) |

## 0.12-pairwise-nli-membership

| # | Experiment | Decision | Hypothesis / purpose | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-pairwise-supported-counterfactual-nli-v1` | **terminal_rejected_pairwise_nli_membership_and_latency** | Compare maximum independent NLI entailment over the anchored tool's registered capability leaves against maximum entailment over counterfactual tool/non-tool leaves; veto only whe… | [issue #378](https://github.com/JDeun/SchemaRouter/issues/378) · [PR #380](https://github.com/JDeun/SchemaRouter/pull/380) · [`02aeefd465`](https://github.com/JDeun/SchemaRouter/commit/02aeefd4656f5b61a948142dfba74f51207bd979) |

## Why the summary page shows fewer rows

[Routing research status](routing-status.md) is intentionally a **current-state summary**. It shows
the standing target, strongest reference points, decisive fresh-confirmation failures, and the
present interpretation. It is not meant to replace the complete ledger.

For full reconstruction, use all three surfaces:

1. this experiment index for the complete catalog;
2. [Design and experiment history](design-and-experiment-history.md) for architectural chronology;
3. the machine-readable ledger and Git history for exact provenance.

This separation keeps the main documentation readable without erasing negative results or abandoned
branches.

## 0.13 schema-derived open-set membership

| # | Experiment | Decision / state | Purpose / interpretation | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.13-v6a-schema-adb` | **terminal_dev_quality_fail** | Schema-only positive views can define endpoint-local adaptive spherical regions that preserve supported natural-language requests while rejecting unsupported requests. | [issue #384](https://github.com/JDeun/SchemaRouter/issues/384) |
| 2 | `0.13-v6b-hard-negative-ellipsoid` | **terminal_dev_quality_fail** | Same-resource hard negatives from the registered capability complement plus a low-rank anisotropic ellipsoid can preserve natural supported requests while rejecting near-domain OOS. | [issue #395](https://github.com/JDeun/SchemaRouter/issues/395) |
| 3 | `0.13-v6c-tied-gaussian-density-ratio` | **terminal_dev_quality_fail** | A tied diagonal Gaussian likelihood ratio between schema positives and complement negatives can avoid absolute-boundary collapse while remaining veto-only. | [issue #397](https://github.com/JDeun/SchemaRouter/issues/397) |
| 4 | `0.13-v6d-component-gaussian-mixture` | **terminal_dev_quality_fail_pr_closed_unmerged** | Registry-fixed endpoint/complement Gaussian components with log-sum-exp mixture evidence can model capability multimodality without changing positive route authority. | [issue #399](https://github.com/JDeun/SchemaRouter/issues/399) |
| 5 | `0.13-v6e-knn-membership` | **terminal_dev_quality_fail_pr_closed_unmerged** | A threshold-free non-parametric k=3 local-neighborhood comparison over schema-positive, complement, and frozen generic background banks can avoid Gaussian assumptions and improve open-set membership. | [issue #401](https://github.com/JDeun/SchemaRouter/issues/401) |
| 6 | `0.13-naturalistic-operation-probe-membership` | **terminal_dev_quality_and_runtime_fail_pr_closed_unmerged** | Naturalistic multilingual linear probes improve broad OOD recognition but remain insufficient for same-domain unsupported-operation membership and supported-route preservation. | [issue #404](https://github.com/JDeun/SchemaRouter/issues/404) · [PR #405](https://github.com/JDeun/SchemaRouter/pull/405) · workflow `36499927289` |
| 7 | `0.13-tool-embed-positive-selector` | **terminal_positive_selector_replacement_fail_pr_closed_unmerged** | Tool-specialized Tool-Embed-0.6B did not outperform same-surface BGE-M3 and missed the runtime gate. | [issue #406](https://github.com/JDeun/SchemaRouter/issues/406) · [PR #407](https://github.com/JDeun/SchemaRouter/pull/407) · workflow `36496824066` |
| 8 | `0.13-relative-multilingual-cross-encoder-membership` | **terminal_dev_quality_and_runtime_fail_pr_closed_unmerged** | Joint query-document relevance over registered, counterfactual, and background documents did not establish open-set membership and was far beyond the CPU runtime budget. | [issue #408](https://github.com/JDeun/SchemaRouter/issues/408) · [PR #411](https://github.com/JDeun/SchemaRouter/pull/411) · workflow `36498385690` |
| 9 | `0.13-frozen-gte-positive-selector` | **terminal_positive_selector_replacement_fail_pr_closed_unmerged** | Historically promising GTE retrieval did not transfer to the fresh registry surface; BGE-M3 won by 16.67 percentage points while GTE retained a good CPU runtime. | [issue #409](https://github.com/JDeun/SchemaRouter/issues/409) · [PR #410](https://github.com/JDeun/SchemaRouter/pull/410) · workflow `36500171432` |
| 10 | `0.13-conformal-multilingual-e5-membership` | **terminal_dev_supported_recall_fail_pr_closed_unmerged** | A fixed alpha=0.01 unsupported-null conformal gate reached the open-set safety/runtime targets, but the scalar E5 catalog score overlapped too strongly and vetoed 87.29% of raw-correct supported winners. | [issue #412](https://github.com/JDeun/SchemaRouter/issues/412) · [PR #413](https://github.com/JDeun/SchemaRouter/pull/413) · workflow `36498943508` |
| 11 | `0.13-v6h-end-to-end-operation-oos-parser` | **terminal_dev_quality_fail_confirmation_unopened_pr_closed_unmerged** | End-to-end multilingual encoder fine-tuning learned tool-vs-background scope well but operation semantics generalized too weakly, especially for near-domain unsupported requests. This closes the 0.13 authoritative parser/veto formulation. | [issue #415](https://github.com/JDeun/SchemaRouter/issues/415) · [PR #416](https://github.com/JDeun/SchemaRouter/pull/416) · workflow `36502279447` |

## 0.14 end-to-end agent utility

| # | Experiment | Decision / state | Purpose / interpretation | Evidence |
| ---: | --- | --- | --- | --- |
| 1 | `0.14-agent-utility-phase-a` | **phase_a_passed_phase_b_authorized** | Top-1 is a poor primary product metric for multi-tool capability retrieval. Top-5 preserved every required capability on the frozen benchmark while schema-context ratio fell to 2.38% of FULL at 250 endpoints. | [issue #418](https://github.com/JDeun/SchemaRouter/issues/418) · [PR #419](https://github.com/JDeun/SchemaRouter/pull/419) · freeze `36507439562` · [`1c0dc93e84`](https://github.com/JDeun/SchemaRouter/commit/1c0dc93e843f6f9bf8a628c80ca95e02efcf5088) |
| 2 | `0.14-b1-local-agent-ab` | **in_progress_no_terminal_claim** | B1 is a reproducible sanity baseline only. Product-level agent utility requires separate stronger-agent B2 replication. | [issue #420](https://github.com/JDeun/SchemaRouter/issues/420) · [PR #421](https://github.com/JDeun/SchemaRouter/pull/421) · freeze `36507439562` |
| 3 | `0.14-b2-strong-agent-replication` | **blocked_until_strong_agent_identity_is_frozen** | Strong-agent replication is required before generalizing B1 utility beyond the small local baseline. | [issue #423](https://github.com/JDeun/SchemaRouter/issues/423) |
| 4 | `0.14-final-answer-quality` | **blocked_until_b1_aggregate_and_b2_model_freeze** | Final-answer factual quality, unit accuracy, provenance and hallucination must be evaluated separately from deterministic tool-use task success. | [issue #424](https://github.com/JDeun/SchemaRouter/issues/424) |

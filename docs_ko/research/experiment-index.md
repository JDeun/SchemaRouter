# 전체 실험 색인

이 페이지는 최신 결과나 가장 높은 성능만 선별하지 않고, SchemaRouter 라우팅 연구의 전체 실험 기록을 공개합니다.

공개 연구 요약 페이지가 "현재 연구가 어디까지 왔는가"에 답한다면, 이 페이지는 "실제로 무엇을 시도했는가"를 보여줍니다.

현재 기계 판독형 실험 기록:

- 별도의 실험으로 등록된 기록: 92건;
- 기존 라우팅 코퍼스 계보: 버전이 명시된 코퍼스 13개;
- 일반적인 버그 수정 커밋은 아키텍처의 불변 조건, 평가 프로토콜 또는 실증적
  주장에 영향을 준 경우가 아니면 독립 실험으로 집계하지 않습니다;
- 실패·대체·무효화·종료된 실험도 숨기지 않고 기록에 유지합니다.

92건의 기록에는 종료된 0.13 V6A–V6H 및 오픈셋 대조 실험과 진행 중인 0.14 에이전트 작업 효용성 연구가 포함됩니다. 종료된 0.13 확인 실험의 평가 데이터는 별도의 명시적 기록이 없는 한 개봉되지 않은 상태로 유지됩니다.

기계적으로 읽을 수 있는 정본은
[`benchmarks/research-experiment-ledger.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json)입니다.
서술형 이력의 정본은
[설계 및 실험 이력](design-and-experiment-history.md)입니다.

**다음에 무엇을 왜 시도해야 하는지**는
[선행연구 기반 로드맵](prior-art-roadmap.md)과 진행 중인 GitHub 이슈 #417을 참고하세요.
과거 0.13 단계의 선행연구 대응 관계는 #388에 남아 있습니다. 이 자료들은
선행연구를 정식 작업 항목에 연결하고 진행 중·다음·대기·보류 상태를 기록하므로,
새 작업 세션에서 이미 종료된 실험을 다시 시작하지 않도록 돕습니다.

## 목적에 맞는 근거 자료 선택

특정 실험 결정의 출처와 이력을 확인하려면 이 원장을 사용하세요. 일반적인 탐색은 아래의 간략한 문서부터 시작하는 것이 좋습니다:

| 확인할 질문 | 참고 문서 |
| --- | --- |
| 현재 근거로 뒷받침할 수 있는 연구 주장은? | [연구 현황](routing-status.md) |
| 논문에 사용할 수 있는 실험 근거는? | [논문 근거 패키지](paper-evidence-package.md) |
| 진행 중이거나 막힌 과제는? | [선행연구 로드맵](prior-art-roadmap.md)과 진행 중인 연구 이슈 |
| 실패 사례를 포함해 실제로 수행한 실험은? | 이 전체 실험 원장 |
| 아키텍처는 어떻게 발전했는가? | [설계 및 실험 이력](design-and-experiment-history.md) |

아래 내용은 의도적으로 기록 보존을 위한 것입니다. 과거의 실패도 재현성을 위해 남기지만, 이를 현재 권장하는 제품 설정으로 해석해서는 안 됩니다.

## 실험 근거를 읽는 방법

Git commit 하나가 experiment 하나와 동일한 것은 아닙니다. 하나의 squashed PR에 implementation, test, preregistration, corpus freeze, calibration, final evidence가 함께 들어갈 수 있고, 반대로 하나의 experiment가 여러 commit이나 workflow run을 필요로 할 수도 있습니다. 따라서 이 원장은 **실험적 의사결정**을 기록 단위로 삼고, 가능한 경우 관련 이슈·PR·리비전·워크플로·아티팩트·소스 파일을 연결합니다.

Repository Git history는 계속 exhaustive engineering record 역할을 합니다.

## 기존 코퍼스 계보

| 코퍼스 | 용도 |
| --- | --- |
| [`decision-routing-v1.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v1.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v2.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v2.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v3.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v3.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v4-operation-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v4-operation-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v5-operation-calibration.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v5-operation-calibration.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v6-operation-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v6-operation-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v7-operation-post-change-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v7-operation-post-change-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v8-operation-alias-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v8-operation-alias-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v9-operation-alias-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v9-operation-alias-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v10-operation-generalization-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v10-operation-generalization-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v11-operation-generalization-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v11-operation-generalization-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v12-operation-contrastive-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v12-operation-contrastive-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |
| [`decision-routing-v13-operation-contrastive-holdout.json`](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/decision-routing-v13-operation-contrastive-holdout.json) | 과거 라우팅·홀드아웃 실험 계보로서 Git 이력과 이후 연구 통제 기록에 보존 |

## Legacy / pre-cycle

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `pre-0.8-no-route-sentinel-ablation` | **sentinel_removed** | 명시적인 `none_of_the_above` 가상 선택지가 검색 후보가 비었을 때 경로 없음 판별을 개선하는지 평가 | [issue #87](https://github.com/JDeun/SchemaRouter/issues/87) · [`e41f57a044`](https://github.com/JDeun/SchemaRouter/commit/e41f57a044182deb374980c28d66863d637a691b) |

## 0.10-operation-contrastive-v1

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-contrastive-bge-v1` | **blind_final_passed_for_optional_profile** | 형제 작업 간 대조를 활용하는 BGE 작업 적합도 평가가 유사 도메인의 미지원 요청 거부율을 보존하면서 지원 요청 라우팅을 개선할 수 있는지 평가 | ledger / Git history |

## 0.10-operation-cascade-v2

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-cheap-first-cascade-v2` | **rejected_on_calibration** | MiniLM 우선 고속 경로와 선택적 BGE 재순위화로 사전 등록한 품질 하한을 유지하면서 CPU 지연시간을 줄일 수 있는지 평가 | ledger / Git history |

## 0.10-operation-graph-projection-v3

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.10-graph-projection-v3` | **rejected_on_fresh_calibration** | 타입 기반 스키마 그래프가 경로 선택 권한을 유지하고 의미 신호는 제한된 보조 근거만 제공할 때 품질과 안전성을 해치지 않으면서 지연시간을 줄일 수 있는지 평가 | [PR #181](https://github.com/JDeun/SchemaRouter/pull/181) |

## 0.11-operation-routing-quality-v4

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.11-v4-fresh-baseline` | baseline_only | 이미 소비한 보정·블라인드 근거를 재사용하지 않고 새 자연어 개발 데이터에서 0.10 이후의 라우팅 병목을 확인 | [PR #187](https://github.com/JDeun/SchemaRouter/pull/187) |
| 2 | `0.11-hierarchical-tool-operation` | rejected_on_development | 도구 도메인 선택과 해당 도구 내 작업 선택을 분리해 미지원 요청 거부를 유지하면서 정확한 경로 선택률을 개선하는지 평가 | [PR #189](https://github.com/JDeun/SchemaRouter/pull/189) |
| 3 | `0.11-accepted-operation-selector` | standalone_candidate_rejected_primitive_retained | 작업 적합성 검사로 이미 등록 경로를 확인한 경우 그 경로가 단일 호출 후보를 결정하도록 하여 선택 보류 규칙을 변경하지 않고 엔드포인트 정확도를 회복할 수 있는지 검토… | [PR #190](https://github.com/JDeun/SchemaRouter/pull/190) |
| 4 | `0.11-stage-signal-diagnostics` | diagnostic_supports_multi_signal_boundary_design | 후보 적합성 점수의 분포를 분석해 회복 가능한 지원 요청 누락을 찾고 전역 유사도 임계값으로 지원 요청과 근접 도메인의 미지원 요청을 구분할 수 있는지 진단… | [`1cf7efc261`](https://github.com/JDeun/SchemaRouter/commit/1cf7efc261b5bcb16b50a8794c8abbf84ed9265c) |
| 5 | `0.11-typed-evidence-infrastructure` | infrastructure_retained_for_next_candidate | 설계 및 평가 과정의 기록 | ledger / Git history |
| 6 | `0.11-route-local-threshold-ablation` | rejected_on_development | 경로별 쌍대 최소 점수 임계값이 작업 범위 제한으로 얻은 정확도 향상을 유지하면서 오픈셋 안전성을 회복할 수 있는지 평가 | [PR #191](https://github.com/JDeun/SchemaRouter/pull/191) |
| 7 | `0.11-nli-boundary-superseded` | superseded_before_result_interpretation | 설계 및 평가 과정의 기록 | [PR #192](https://github.com/JDeun/SchemaRouter/pull/192) |
| 8 | `0.11-pairwise-tool-hierarchy` | rejected_on_development | 도구 쌍대 순위화가 지원 요청의 70% 기준은 넘겼지만 오픈셋 기능 경계를 제공하지 못했고 거부율·잘못된 경로 기준에서 크게 미달함 | [PR #193](https://github.com/JDeun/SchemaRouter/pull/193) |
| 9 | `0.11-direct-multilingual-nli-boundary` | rejected_on_development | 보수적인 함의 판정 임계값은 미지원 요청 거부를 개선했지만 지원 요청 재현율을 크게 낮췄으므로 시험한 직접 NLI 방식을 작업 선택기·게이트로 사용하기 어려움 | [PR #194](https://github.com/JDeun/SchemaRouter/pull/194) |
| 10 | `0.11-bounded-retrieve-rerank-architecture` | architecture_implemented_diagnostic_pending | 설계 및 평가 과정의 기록 | [PR #195](https://github.com/JDeun/SchemaRouter/pull/195) · [`90af3e1fce`](https://github.com/JDeun/SchemaRouter/commit/90af3e1fce3bf29f45fd3347c14afc2603b37d5e) |
| 11 | `0.11-bounded-rerank-score-diagnostic` | ranking_headroom_validated_latency_optimization_required | 설계 및 평가 과정의 기록 | [PR #205](https://github.com/JDeun/SchemaRouter/pull/205) · [`f43535b6ef`](https://github.com/JDeun/SchemaRouter/commit/f43535b6ef0acbc5492b9791e6757e28a343d9fa) |
| 12 | `0.11-winner-only-threshold-semantics` | mechanism_merged_into_active_research_stack | 설계 및 평가 과정의 기록 | [PR #208](https://github.com/JDeun/SchemaRouter/pull/208) |
| 13 | `0.11-evidence-projector-active-stack` | infrastructure_merged_into_active_research_stack | 설계 및 평가 과정의 기록 | ledger / Git history |
| 14 | `0.11-bounded-rerank-width-ablation` | selected_width_2_by_preregistered_smallest_passing_width_rule | 설계 및 평가 과정의 기록 | [PR #216](https://github.com/JDeun/SchemaRouter/pull/216) · [`9f4dbff423`](https://github.com/JDeun/SchemaRouter/commit/9f4dbff423cdcb9151d00d1b15586f9b3d766235) |
| 15 | `0.11-joint-score-margin-boundary` | not_selected | 동일한 잘못된 경로 허용량에서 점수·마진 결합 게이트의 이득은 약 0.35%포인트에 불과해 후보 폭·지연시간 최적화 전에 더 큰 경로별 조정 공간을 정당화하기 어려움… | ledger / Git history |
| 16 | `0.11-width2-winner-gate-executable` | rejected_on_development_latency_gate | 후보 폭 2의 제한된 의미 검색과 점수 기반 BGE 순위 결정·게이트가 지연시간의 실질적인 악화 없이 0.11 개발 품질 기준을 충족할 수 있는지 평가 | [PR #228](https://github.com/JDeun/SchemaRouter/pull/228) · [`fdaf3f77e9`](https://github.com/JDeun/SchemaRouter/commit/fdaf3f77e95b504e81739c69cd1d9889d36afabb) |
| 17 | `0.11-cheap-action-only-evidence-diagnostic` | retain_as_cheap_bounded_selector_or_auxiliary_evidence_not_global_direct_fast_path | 엔드포인트 작업명과 신뢰된 별칭만 사용하는 저비용 다국어 임베딩이 BGE보다 낮은 지연시간으로 독립적인 라우팅 근거를 제공할 수 있는지 진단 | [PR #230](https://github.com/JDeun/SchemaRouter/pull/230) · [`521dcc65e0`](https://github.com/JDeun/SchemaRouter/commit/521dcc65e0269d68c76a372606f8d22b2ac57aa1) |
| 18 | `0.11-action-guided-single-pair-bge-diagnostic` | rejected_on_supported_recall | 저비용 작업명 근거로 이미 허용된 폭 2의 후보 하나를 고른 후 BGE 쌍 하나만 채점해 CPU 지연시간의 긴 꼬리를 줄이는지 평가 | [issue #231](https://github.com/JDeun/SchemaRouter/issues/231) · [PR #232](https://github.com/JDeun/SchemaRouter/pull/232) |
| 19 | `0.11-bounded-action-embedding-diagnostic` | rejected_on_open_set_supported_recall | 후보 폭 2의 허용된 검색 단계에서 BGE를 캐시된 작업명 전용 MiniLM 임베딩 근거로 교체 | [issue #233](https://github.com/JDeun/SchemaRouter/issues/233) · [PR #236](https://github.com/JDeun/SchemaRouter/pull/236) |
| 20 | `0.11-minilm-dual-view-diagnostic` | rejected_backbone_capacity_insufficient | 하나의 MiniLM 질의 임베딩을 캐시된 스키마·도메인 표현과 작업명 전용 경로 표현에 비교해 순위 근거와 오픈셋 신뢰도를 분리하는지 진단 | [issue #240](https://github.com/JDeun/SchemaRouter/issues/240) · [PR #241](https://github.com/JDeun/SchemaRouter/pull/241) |
| 21 | `0.11-multilingual-embedding-backbone-screen` | bge_m3_selected_for_strict_open_set_optimization | 두 관점의 라우팅 아키텍처는 고정하고 다국어 임베딩 모델의 용량만 변경하여 비교 | [issue #242](https://github.com/JDeun/SchemaRouter/issues/242) · [PR #243](https://github.com/JDeun/SchemaRouter/pull/243) |
| 22 | `0.11-gte-winner-bge-rejector` | rejected_on_supported_recall | 대용량 GTE로 최상위 경로 하나를 선택하고 BGE 크로스 인코더 쌍 하나를 미지원 작업 거부 판단에만 사용 | [issue #244](https://github.com/JDeun/SchemaRouter/issues/244) · [PR #249](https://github.com/JDeun/SchemaRouter/pull/249) |
| 23 | `0.11-bge-m3-budget6-executable-confirmation` | not_promoted_literal_freeze_missed_by_one_case | 지원되는 `papers.citations` 사례 하나의 점수가 동결 임계값보다 약 1.35e-7 낮았음. 계획기·직접 호출 일치성과 안전성 기준은 통과했으나 정해진 960개 정답 기준은… | [issue #245](https://github.com/JDeun/SchemaRouter/issues/245) · [PR #247](https://github.com/JDeun/SchemaRouter/pull/247) |
| 24 | `0.11-bge-m3-fine-fusion-strict` | no_fusion_weight_reached_85_percent_strict_target | 사전 등록된 최선의 엄격한 설정은 정확 경로율 83.77%, 근접 도메인 거부율 98.96%, 잘못된 경로 비율 0.93%였음. 범위 외 보간이나 사후 가중치 조정은 허용하지 않음 | [issue #246](https://github.com/JDeun/SchemaRouter/issues/246) · [PR #248](https://github.com/JDeun/SchemaRouter/pull/248) · [`9d6f5bdc18`](https://github.com/JDeun/SchemaRouter/commit/9d6f5bdc18c933a35d4f8f9983c12c850ab9b0fb) |
| 25 | `0.11-conditional-zero-false-rejected-winner-rescue` | rejected_zero_false_rescue_recovers_only_5_of_required_15 | 설계 및 평가 과정의 기록 | [issue #255](https://github.com/JDeun/SchemaRouter/issues/255) · [PR #258](https://github.com/JDeun/SchemaRouter/pull/258) |
| 26 | `0.11-route-local-stable-bge-m3-fusion` | rejected_strict_boundary_below_85_percent_despite_90_54_raw_ceiling | 사전에 등록한 #246 탐색 공간에서 경로별 융합 가중치를 선택하고 중간값·정규화 임계값으로 점수 경계 문제를 줄여 남은 정확 경로율 차이를 회복할 수 있는지 검토… | [issue #256](https://github.com/JDeun/SchemaRouter/issues/256) · [PR #257](https://github.com/JDeun/SchemaRouter/pull/257) |
| 27 | `0.11-numerically-robust-threshold-freeze-policy` | required_for_future_frozen_candidates | 설계 및 평가 과정의 기록 | [issue #253](https://github.com/JDeun/SchemaRouter/issues/253) |
| 28 | `0.11-bge-m3-robust-budget6-executable-confirmation` | confirmed_as_numerically_robust_strict_base_for_conditional_rescue | 설계 및 평가 과정의 기록 | [issue #259](https://github.com/JDeun/SchemaRouter/issues/259) · [`9e9b1049ea`](https://github.com/JDeun/SchemaRouter/commit/9e9b1049eac779adbc5781bfc45a447966ae32e8) |
| 29 | `0.11-cross-model-zero-false-abstention-rescue` | gte_agreement_bge_selected_for_frozen_confirmation | 설계 및 평가 과정의 기록 | [issue #262](https://github.com/JDeun/SchemaRouter/issues/262) · [PR #263](https://github.com/JDeun/SchemaRouter/pull/263) |
| 30 | `0.11-zero-false-cross-model-frozen-candidate` | rejected_surface_fragile_positive_open_set_boundary | 설계 및 평가 과정의 기록 | [issue #265](https://github.com/JDeun/SchemaRouter/issues/265) · [PR #270](https://github.com/JDeun/SchemaRouter/pull/270) |
| 31 | `0.11-robust-base-winner-crossencoder-rescue` | rejected_safe_but_insufficient_rescue | 설계 및 평가 과정의 기록 | [issue #266](https://github.com/JDeun/SchemaRouter/issues/266) |
| 32 | `0.11-native-bge-m3-abstention-geometry-rescue` | rejected_native_geometry_insufficient | 설계 및 평가 과정의 기록 | [issue #271](https://github.com/JDeun/SchemaRouter/issues/271) |
| 33 | `0.11-typed-contradiction-only-nli-veto` | rejected_generic_nli_neutral_on_supported_and_unsupported | 설계 및 평가 과정의 기록 | [issue #273](https://github.com/JDeun/SchemaRouter/issues/273) |
| 34 | `0.11-explicit-negative-capability-prototype-veto` | rejected_combined_winner_domain_ood_veto | 설계 및 평가 과정의 기록 | [issue #275](https://github.com/JDeun/SchemaRouter/issues/275) · [PR #276](https://github.com/JDeun/SchemaRouter/pull/276) |
| 35 | `0.11-global-signed-capability-prototype-bank` | rejected_global_signed_prototype_evidence_too_coarse | 설계 및 평가 과정의 기록 | [issue #277](https://github.com/JDeun/SchemaRouter/issues/277) · [PR #278](https://github.com/JDeun/SchemaRouter/pull/278) |
| 36 | `0.11-dual-signed-negative-openworld` | rejected_scalar_signed_evidence_overlap | 설계 및 평가 과정의 기록 | [issue #279](https://github.com/JDeun/SchemaRouter/issues/279) · [PR #280](https://github.com/JDeun/SchemaRouter/pull/280) |
| 37 | `0.11-rank-based-capability-set-openworld` | rejected_fixed_prototype_heuristics_terminated | 설계 및 평가 과정의 기록 | [issue #281](https://github.com/JDeun/SchemaRouter/issues/281) · [PR #283](https://github.com/JDeun/SchemaRouter/pull/283) · [`944df2e0f2`](https://github.com/JDeun/SchemaRouter/commit/944df2e0f2dc8617e7b97e6a38d4e2f5684f5324) |
| 38 | `0.11-grouped-oof-learned-winner-verifier` | promote_hgb_p0_500_to_separate_frozen_candidate | 설계 및 평가 과정의 기록 | [issue #285](https://github.com/JDeun/SchemaRouter/issues/285) · [PR #286](https://github.com/JDeun/SchemaRouter/pull/286) · [`cfaafb84bb`](https://github.com/JDeun/SchemaRouter/commit/cfaafb84bb651a6d6d38c4ce741f05ac61f37e9e) |
| 39 | `0.11-external-qwen3-semantic-capability-verifier` | reject | 설계 및 평가 과정의 기록 | [issue #289](https://github.com/JDeun/SchemaRouter/issues/289) · [PR #290](https://github.com/JDeun/SchemaRouter/pull/290) · [`68e812ab5c`](https://github.com/JDeun/SchemaRouter/commit/68e812ab5c72bd42664e21f8c9f62a760465cb03) |
| 40 | `0.11-frozen-hgb-winner-verifier-candidate` | rejected_fresh_surface_generalization_failure | 설계 및 평가 과정의 기록 | [issue #287](https://github.com/JDeun/SchemaRouter/issues/287) · [PR #288](https://github.com/JDeun/SchemaRouter/pull/288) · [`e5b10ee01e`](https://github.com/JDeun/SchemaRouter/commit/e5b10ee01ec23af6113c562b51e1db0c6d003d7a) |
| 41 | `0.11-system-one-provider-contract` | accepted_reusable_infrastructure | 설계 및 평가 과정의 기록 | [issue #291](https://github.com/JDeun/SchemaRouter/issues/291) · [PR #292](https://github.com/JDeun/SchemaRouter/pull/292) · [`7f4118ea05`](https://github.com/JDeun/SchemaRouter/commit/7f4118ea059ab448ca132a3ef83b7a43135318c8) |
| 42 | `0.11-pluggable-system-one-routing` | direct_laya_rejected_parent_remains_open_for_system_one_comparison | 설계 및 평가 과정의 기록 | [issue #293](https://github.com/JDeun/SchemaRouter/issues/293) · [PR #294](https://github.com/JDeun/SchemaRouter/pull/294) · [`48e329ee94`](https://github.com/JDeun/SchemaRouter/commit/48e329ee949d0d7a42d93a7c06c7ecbc62edfedc) |
| 43 | `0.11-kev-08b-choice-noul-screen` | no_quality_result_runtime_nonviable | 설계 및 평가 과정의 기록 | [issue #299](https://github.com/JDeun/SchemaRouter/issues/299) · [PR #300](https://github.com/JDeun/SchemaRouter/pull/300) |
| 44 | `0.11-pinned-laya-noul-veto` | reject | 설계 및 평가 과정의 기록 | [issue #301](https://github.com/JDeun/SchemaRouter/issues/301) · [PR #302](https://github.com/JDeun/SchemaRouter/pull/302) · [`46af3c3d01`](https://github.com/JDeun/SchemaRouter/commit/46af3c3d0156b7b7bfd40686aa5639571f91a936) |
| 45 | `0.11-laya-choice-noul-full-catalog` | superseded_by_301 | 설계 및 평가 과정의 기록 | [issue #295](https://github.com/JDeun/SchemaRouter/issues/295) · [PR #296](https://github.com/JDeun/SchemaRouter/pull/296) |
| 46 | `0.11-top4-typed-capability-routing` | same_laya_variant_dominated; provider_neutral_contingency_only | 설계 및 평가 과정의 기록 | [issue #303](https://github.com/JDeun/SchemaRouter/issues/303) · [PR #310](https://github.com/JDeun/SchemaRouter/pull/310) |
| 47 | `0.11-generic-decision-callable-benchmark` | accepted_reusable_infrastructure | 설계 및 평가 과정의 기록 | [issue #304](https://github.com/JDeun/SchemaRouter/issues/304) · [PR #305](https://github.com/JDeun/SchemaRouter/pull/305) · [`c9678b95a6`](https://github.com/JDeun/SchemaRouter/commit/c9678b95a6dc592a1c3b850a6aea8b1675ff94a4) |
| 48 | `0.11-anyjev-l0-content-free-noul-veto` | await_realistic_runtime_before_execution | 설계 및 평가 과정의 기록 | [issue #311](https://github.com/JDeun/SchemaRouter/issues/311) · [PR #313](https://github.com/JDeun/SchemaRouter/pull/313) |
| 49 | `0.11-bge-plus-kev-global-noul` | source_kev_analysis_missing | 설계 및 평가 과정의 기록 | [issue #314](https://github.com/JDeun/SchemaRouter/issues/314) |
| 50 | `0.11-lightweight-negative-gte-offline-compose` | pass_promote_executable | 설계 및 평가 과정의 기록 | [issue #322](https://github.com/JDeun/SchemaRouter/issues/322) · [PR #323](https://github.com/JDeun/SchemaRouter/pull/323) |
| 51 | `0.11-lightweight-negative-gte-executable` | pass_dev_promote_fresh | 설계 및 평가 과정의 기록 | [issue #324](https://github.com/JDeun/SchemaRouter/issues/324) · [PR #325](https://github.com/JDeun/SchemaRouter/pull/325) |
| 52 | `0.11-lightweight-bge-gte-frozen-fresh-confirmation` | reject_after_fresh_failure | 설계 및 평가 과정의 기록 | [issue #326](https://github.com/JDeun/SchemaRouter/issues/326) · [PR #327](https://github.com/JDeun/SchemaRouter/pull/327) · [`b19d7b0255`](https://github.com/JDeun/SchemaRouter/commit/b19d7b0255ee9717464b6fa65ce1ebdeaf58a1bd) |
| 53 | `0.11-bge-m3-colbert-operation-contract` | reject | 설계 및 평가 과정의 기록 | [issue #328](https://github.com/JDeun/SchemaRouter/issues/328) · [PR #329](https://github.com/JDeun/SchemaRouter/pull/329) · [`4c72f2dd19`](https://github.com/JDeun/SchemaRouter/commit/4c72f2dd1939edb6ecf8415d620dbb5d58683fa0) |
| 54 | `0.11-bge-registry-alias-envelope` | reject | 레지스트리에서 도출한 형제 작업 대조는 재현율을 유지하지만 미지원 요청을 수용함. 레지스트리 응집도를 이용한 거부는 지원 요청 정확도를 약 24%로 낮추는 방식으로만 작동하며… | [issue #332](https://github.com/JDeun/SchemaRouter/issues/332) · [PR #333](https://github.com/JDeun/SchemaRouter/pull/333) · [`fa091f4329`](https://github.com/JDeun/SchemaRouter/commit/fa091f43296eb1ca680f39921010482275bb4cda) |
| 55 | `0.11-bge-gte-threshold-free-consensus` | reject | 서로 다른 모델의 Top-1 일치는 미지원 기능 판정 근거보다 경로 선택 신뢰도에 가까움. 강한 순위화기 두 개가 그럴듯한 등록 경로 하나에 함께 동의하는 사례가 자주 나타남… | [issue #336](https://github.com/JDeun/SchemaRouter/issues/336) · [PR #337](https://github.com/JDeun/SchemaRouter/pull/337) · [`d25f427569`](https://github.com/JDeun/SchemaRouter/commit/d25f427569fc4419a72963c6f31994fa170805f6) |
| 56 | `0.11-registry-compiled-capability-verifier` | terminal_rejected_overconservative_veto | 제공자 중립적인 기능 중간 표현과 범용 합성 반사실 근거를 이용해 새로 등록된 네이티브·OpenAPI·MCP 도구의 미지원 작업을 거부할 수 있는지 평가… | [issue #338](https://github.com/JDeun/SchemaRouter/issues/338) · [PR #341](https://github.com/JDeun/SchemaRouter/pull/341) · [`ef75100abc`](https://github.com/JDeun/SchemaRouter/commit/ef75100abc1bb03a80ef2d7cfbd9d463accfb623) |

## 0.12-query-first-typed-capability

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-query-first-typed-frame-v1` | **terminal_rejected_insufficient_open_set_rejection** | 레지스트리와 독립적인 명시적 요청 프레임과 도구 내부의 결정론적 계약 필터링으로 별도 학습 없이 동일 도메인의 미지원 작업을 빈 기능 집합으로 분류할 수 있는지 평가… | [issue #347](https://github.com/JDeun/SchemaRouter/issues/347) · [PR #348](https://github.com/JDeun/SchemaRouter/pull/348) · [`ef0e0a567f`](https://github.com/JDeun/SchemaRouter/commit/ef0e0a567f12129bf9f4b003d13f9f6e9679a216) |

## 0.12-semantic-action-ontology

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-semantic-action-ontology-v1` | **terminal_rejected_flat_semantic_argmax** | 동결된 레지스트리 독립 다국어 작업 온톨로지가 도구 내부의 결정론적 기능 대응에 앞서 요청의 작업 의미를 분류할 수 있는지 평가… | [issue #349](https://github.com/JDeun/SchemaRouter/issues/349) · [PR #352](https://github.com/JDeun/SchemaRouter/pull/352) · [`38ee755756`](https://github.com/JDeun/SchemaRouter/commit/38ee7557565983746e33741897e6168bf4f35643) |

## 0.12-hierarchical-capability-ontology

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-hierarchical-capability-ontology-v1` | **terminal_rejected_hard_ontology_filter** | 루트·리프 제약과 대조적인 다국어 원형을 갖춘 계층적 실행 가능 기능 온톨로지가 등록된 실행 경계를 유지하면서 오픈셋 집합 소속 판단을 개선할 수 있는지 평가… | [issue #354](https://github.com/JDeun/SchemaRouter/issues/354) · [PR #357](https://github.com/JDeun/SchemaRouter/pull/357) · [`250845bba0`](https://github.com/JDeun/SchemaRouter/commit/250845bba058a704ab50cdde43326cc1e5c26d62) |

## 0.12-asymmetric-ontology-veto

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-asymmetric-ontology-veto-v1` | **terminal_rejected_high_precision_low_recall_asymmetric_veto** | 동결된 BGE-M3 원시 Top-1을 유일한 긍정 경로 선택자로 유지하고 온톨로지 근거는 고정된 독립 동의 규칙에 따른 비대칭 미지원 기능 거부 판단에만 사용하는지 평가… | [issue #358](https://github.com/JDeun/SchemaRouter/issues/358) · [PR #360](https://github.com/JDeun/SchemaRouter/pull/360) · [`759359882c`](https://github.com/JDeun/SchemaRouter/commit/759359882c3deb1be310fc540bbb1780b1543885) |

## 0.12-capability-set-membership-veto

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-capability-set-membership-consensus-v1` | **terminal_rejected_membership_consensus_insufficient** | 정확히 같은 미지원 리프의 일치를 요구하는 대신 기준 도구의 기능 집합 소속에 대한 합의를 사용하되 긍정 경로 선택 권한은 동결된 BGE-M3에만 유지 | [issue #363](https://github.com/JDeun/SchemaRouter/issues/363) · [PR #364](https://github.com/JDeun/SchemaRouter/pull/364) · [`f198f896c4`](https://github.com/JDeun/SchemaRouter/commit/f198f896c44860c27ce14b4c88200096ef0b754f) |

## 0.12-external-zeroshot-membership

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-external-multilingual-zeroshot-membership-v1` | **terminal_rejected_multiclass_outside_label_no_open_set_boundary** | 외부에서 사전 학습한 소형 다국어 제로샷 분류기로 질의가 BGE 기준 도구에 등록된 유한한 기능 집합에 속하는지 평가… | [issue #371](https://github.com/JDeun/SchemaRouter/issues/371) · [PR #372](https://github.com/JDeun/SchemaRouter/pull/372) · [`5e6dde0c38`](https://github.com/JDeun/SchemaRouter/commit/5e6dde0c3860ff46f0961c74233d7196e6c86f59) |

## 0.12-set-conditioned-binary-entailment

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-set-conditioned-binary-entailment-v1` | **terminal_rejected_all_not_entailment** | 기준 도구의 전체 등록 기능 집합을 대상으로 NLI 문장 쌍 하나를 판정해 함의되면 동결된 BGE-M3 경로를 유지하고 함의되지 않으면 `NO_ROUTE`로 거부… | [issue #374](https://github.com/JDeun/SchemaRouter/issues/374) · [PR #375](https://github.com/JDeun/SchemaRouter/pull/375) · [`e61058d0aa`](https://github.com/JDeun/SchemaRouter/commit/e61058d0aa31819bf99b182f4bd5947dd0d11fab) |

## 0.12-independent-capability-entailment

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-independent-per-capability-entailment-v1` | **terminal_rejected_independent_entailment_over_veto** | 버전을 고정한 다국어 NLI 모델로 등록된 기능 리프 각각을 독립 평가해 하나라도 함의되면 동결된 BGE-M3 원시 Top-1을 유지하고 그렇지 않으면 거부… | [issue #377](https://github.com/JDeun/SchemaRouter/issues/377) · [PR #379](https://github.com/JDeun/SchemaRouter/pull/379) · [`a872c9602d`](https://github.com/JDeun/SchemaRouter/commit/a872c9602dcad959ea1bf10f16a052592754d4ae) |

## 0.12-pairwise-nli-membership

| # | 실험 | 판정 | 가설 / 목적 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.12-pairwise-supported-counterfactual-nli-v1` | **terminal_rejected_pairwise_nli_membership_and_latency** | 기준 도구의 등록된 기능 리프와 반사실 도구·비도구 리프에서 각각 가장 높은 NLI 함의 점수를 비교해 사전 규칙에 따라 거부 여부만 결정… | [issue #378](https://github.com/JDeun/SchemaRouter/issues/378) · [PR #380](https://github.com/JDeun/SchemaRouter/pull/380) · [`02aeefd465`](https://github.com/JDeun/SchemaRouter/commit/02aeefd4656f5b61a948142dfba74f51207bd979) |

## 요약 페이지에 표시된 결과가 적은 이유

[라우팅 연구 현황](routing-status.md)은 최신 상태의 요약 자료입니다.
현재 유지되는 목표, 가장 강한 비교 기준, 새 확인 실험에서 드러난 결정적인 실패,
그리고 그에 대한 현재 해석을 정리합니다. 전체 실험 원장을 대체하는 문서는 아닙니다.

전체 연구 과정을 재구성하려면 다음 세 자료를 함께 확인하세요:

1. 실험 항목을 빠짐없이 확인할 수 있는 이 전체 색인
2. 아키텍처 변화와 결정 과정을 기록한 [설계 및 실험 이력](design-and-experiment-history.md)
3. 정확한 출처와 커밋 이력을 확인할 수 있는 기계 판독형 실험 원장 및 Git 기록

이 자료들을 분리하면 부정적인 결과나 중단된 실험 계열을 삭제하지 않으면서도 기본 설명 문서를 읽기 쉽게 유지할 수 있습니다.

## 0.13 스키마 기반 오픈셋 소속성

| # | 실험 | 판정 / 상태 | 목적 / 해석 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.13-v6a-schema-adb` | terminal_dev_quality_fail | 스키마에서 얻은 긍정 사례만으로 엔드포인트별 적응형 구형 영역을 구성해, 지원되는 자연어 요청을 보존하면서 미지원 요청을 거부할 수 있는지 검증 | [issue #384](https://github.com/JDeun/SchemaRouter/issues/384) |
| 2 | `0.13-v6b-hard-negative-ellipsoid` | terminal_dev_quality_fail | 등록된 기능의 여집합에서 구성한 동일 리소스 부정 사례와 저차원 비등방성 타원체를 결합해 지원 요청을 보존하고 근접 도메인 미지원 작업을 거부할 수 있는지 검증 | [issue #395](https://github.com/JDeun/SchemaRouter/issues/395) |
| 3 | `0.13-v6c-tied-gaussian-density-ratio` | terminal_dev_quality_fail | 스키마 양성 사례와 여집합 음성 사례 사이의 공유 대각 가우시안 우도비가 긍정 경로를 변경하지 않으면서 절대 경계 붕괴를 피할 수 있는지 검증 | [issue #397](https://github.com/JDeun/SchemaRouter/issues/397) |
| 4 | `0.13-v6d-component-gaussian-mixture` | terminal_dev_quality_fail_pr_closed_unmerged | 레지스트리로 고정한 엔드포인트·여집합 가우시안 성분과 로그합지수 혼합 근거를 이용해 긍정 경로 선택 권한을 바꾸지 않고 기능의 다봉성을 표현할 수 있는지 검증 | [issue #399](https://github.com/JDeun/SchemaRouter/issues/399) |
| 5 | `0.13-v6e-knn-membership` | terminal_dev_quality_fail_pr_closed_unmerged | 스키마 양성·여집합·동결된 범용 배경 데이터에서 임계값 없는 k=3 국소 이웃을 비교해 가우시안 가정을 제거하고 오픈셋 구분을 개선할 수 있는지 검증 | [issue #401](https://github.com/JDeun/SchemaRouter/issues/401) |
| 6 | `0.13-naturalistic-operation-probe-membership` | terminal_dev_quality_and_runtime_fail_pr_closed_unmerged | 자연스러운 다국어 선형 탐침은 광범위한 분포 밖 요청 탐지를 개선했지만 동일 도메인의 미지원 작업 판별과 지원 경로 보존에는 부족했음 | [issue #404](https://github.com/JDeun/SchemaRouter/issues/404) · [PR #405](https://github.com/JDeun/SchemaRouter/pull/405) · workflow `36499927289` |
| 7 | `0.13-tool-embed-positive-selector` | terminal_positive_selector_replacement_fail_pr_closed_unmerged | 도구 전용 Tool-Embed-0.6B는 같은 평가 데이터의 BGE-M3보다 우수하지 않았고 실행시간 게이트도 통과하지 못함 | [issue #406](https://github.com/JDeun/SchemaRouter/issues/406) · [PR #407](https://github.com/JDeun/SchemaRouter/pull/407) · workflow `36496824066` |
| 8 | `0.13-relative-multilingual-cross-encoder-membership` | terminal_dev_quality_and_runtime_fail_pr_closed_unmerged | 등록·반사실·배경 문서 사이의 질의-문서 관련도를 통합해도 오픈셋 집합 소속을 입증하지 못했고 CPU 실행시간 예산도 크게 초과했음 | [issue #408](https://github.com/JDeun/SchemaRouter/issues/408) · [PR #411](https://github.com/JDeun/SchemaRouter/pull/411) · workflow `36498385690` |
| 9 | `0.13-frozen-gte-positive-selector` | terminal_positive_selector_replacement_fail_pr_closed_unmerged | 이전 연구에서 유망했던 GTE 검색은 새로운 레지스트리 평가 데이터에 일반화되지 않았음. CPU 실행시간은 양호했지만 정확도는 BGE-M3가 16.67%포인트 높았음 | [issue #409](https://github.com/JDeun/SchemaRouter/issues/409) · [PR #410](https://github.com/JDeun/SchemaRouter/pull/410) · workflow `36500171432` |
| 10 | `0.13-conformal-multilingual-e5-membership` | terminal_dev_supported_recall_fail_pr_closed_unmerged | alpha=0.01로 고정한 미지원 요청용 컨포멀 게이트는 오픈셋 안전성·실행시간 목표에 도달했지만 E5 카탈로그 점수가 크게 겹쳐 원래 정답이던 지원 요청의 87.29%를 거부했음 | [issue #412](https://github.com/JDeun/SchemaRouter/issues/412) · [PR #413](https://github.com/JDeun/SchemaRouter/pull/413) · workflow `36498943508` |
| 11 | `0.13-v6h-end-to-end-operation-oos-parser` | terminal_dev_quality_fail_confirmation_unopened_pr_closed_unmerged | 다국어 인코더 엔드투엔드 미세조정은 도구와 배경의 범위를 잘 구분했지만 특히 근접 도메인 미지원 요청의 작업 의미 일반화가 부족했음. 이로써 0.13의 최종 파서·거부 판단 설계가 종료됨 | [issue #415](https://github.com/JDeun/SchemaRouter/issues/415) · [PR #416](https://github.com/JDeun/SchemaRouter/pull/416) · workflow `36502279447` |

## 0.14 엔드투엔드 에이전트 작업 효용성

> 아래 판정 코드는 기계 판독형 원장에 기록된 **당시의 동결된 연구 단계·등록 상태**를 그대로 보존합니다. 현재 실험 진행 상황은 [연구 현황](routing-status.md)과 [컨베이어 #500](https://github.com/JDeun/SchemaRouter/issues/500)을 확인하세요. 원장에 과거 `blocked` 상태가 남아 있다고 해서 현재 연구가 계속 차단됐다는 의미는 아닙니다.

| # | 실험 | 판정 / 상태 | 목적 / 해석 | 근거 |
| ---: | --- | --- | --- | --- |
| 1 | `0.14-agent-utility-phase-a` | phase_a_passed_phase_b_authorized | 여러 도구가 필요한 기능 검색에서 Top-1은 제품의 주된 성능 지표로 부적절함. B1-v2 과제 계약을 다시 동결한 뒤 Top-5는 필요한 모든 기능을 유지했으며 엔드포인트 250개에서 스키마 컨텍스트는 FULL의 2.383%였음 | [issue #418](https://github.com/JDeun/SchemaRouter/issues/418) · [PR #419](https://github.com/JDeun/SchemaRouter/pull/419) · freeze `36507439562` · [`1c0dc93e84`](https://github.com/JDeun/SchemaRouter/commit/1c0dc93e843f6f9bf8a628c80ca95e02efcf5088) |
| 2 | `0.14-b1-local-agent-ab` | running_b1_v2_protocol_validated_canonical_execution | B1 v2는 정식 집계 이전에 명시적인 사용자 인수 계약과 도구 관측값의 인과관계를 수정한 소형 모델 정상 동작 기준 실험 | [issue #420](https://github.com/JDeun/SchemaRouter/issues/420) · [PR #421](https://github.com/JDeun/SchemaRouter/pull/421) · canonical run `36529108855` · task SHA `bc0b78ff...` |
| 3 | `0.14-b2-strong-agent-replication` | blocked_until_strong_agent_identity_is_frozen | 소형 로컬 모델의 B1 결과를 확대 해석하기 전에 강한 에이전트 모델에서의 재현 검증이 필요함 | [issue #423](https://github.com/JDeun/SchemaRouter/issues/423) |
| 4 | `0.14-final-answer-quality` | blocked_until_b1_aggregate_and_b2_model_freeze | 최종 답변의 사실성·단위 정확성·출처·환각은 결정론적 도구 사용 과제 통과율과 별도로 평가해야 함 | [issue #424](https://github.com/JDeun/SchemaRouter/issues/424) |
| 5 | `0.14-corrective-state-aware-reretrieval` | no_execution_before_420_terminal | 타입이 지정된 제한적 관측값으로 실행 상태를 인식해 재검색하는 방법과 정적 후보 노출을 비교하되 검색 자체에는 실행 권한을 부여하지 않음 | [issue #431](https://github.com/JDeun/SchemaRouter/issues/431) |
| 6 | `0.14-large-held-out-generalization` | freeze_sample_size_and_generation_protocol_after_b1_without_using_b1_row_failures | 일반화 및 불확실성을 평가하도록 독립적으로 동결한 대규모 다국어 홀드아웃 평가 데이터를 구성 | [issue #432](https://github.com/JDeun/SchemaRouter/issues/432) |
| 7 | `0.14-adaptive-shortlist-depth` | no_execution_before_b1_b2_fixed_k_evidence | 고정 K 실험 근거 이후에만 사전 등록된 질의별 적응형 후보 깊이를 시험하며 B1 오류를 보고 정책을 도출하지 않음 | [issue #430](https://github.com/JDeun/SchemaRouter/issues/430) |
| 8 | `0.14-public-topk-retrieval-api` | do_not_promote_before_b1_aggregate | 에이전트 오케스트레이션과 실행 권한을 핵심 검색기 밖에 유지하면서 타입 기반 Top-K 공개 검색 API를 일급 기능으로 준비 | [issue #428](https://github.com/JDeun/SchemaRouter/issues/428) |
| 9 | `0.14-output-field-projection` | preregistered_dev_screen_authorized_confirmation_gated_on_b2_terminal | 이전 실험과 독립적으로 출력 필드 투영 효과를 측정함. B1은 노출한 도구 수, #434는 기능 표현을 변경했지만 여기서는 질의·노출·경로·원시 응답을 고정하고 실행 도구가 반환하는 필드만 변경 | [issue #506](https://github.com/JDeun/SchemaRouter/issues/506) · [protocol](field-projection-answer-quality.md) |
| 10 | `0.14-output-field-projection-successor-screen` | preregistered_instrument_gate_frozen_before_any_candidate_runs | #506의 실행 환경은 도구를 호출하지 않고 답변 형식만 생성해 해석 가능한 결과를 내지 못했음. 후속 검사는 관측 결과를 보고 모델을 선택하지 않고 별도 평가 데이터의 동결된 기능 게이트로 계측 모델을 선정 | [issue #510](https://github.com/JDeun/SchemaRouter/issues/510) · [protocol](successor-screen.md) |

## Evidence-to-Action 계약 회귀 검증

Issue #1203 / PR #1204에서 별도의 deterministic execution-boundary 실험을 추가했습니다. 고정된 8개 case에서 vanilla, routing-only, typed evidence gate를 비교합니다. 이 baseline은 regression artifact이며 위 routing experiment count에 포함하지 않고 SafeActBench 재현으로도 취급하지 않습니다. 정본 설명과 한계는 [Evidence-to-Action 경계](evidence-to-action.md)와 `benchmarks/evidence-to-action-v1/`에 기록합니다.

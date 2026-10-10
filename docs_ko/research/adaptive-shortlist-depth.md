# 0.14 adaptive capability shortlist depth

## Terminal research status — 2026-09-30

원래 **score-gap adaptive-depth** 가설은 selected adaptive policy 없이 종료됐습니다. 현재 evidence는 다른 결론을 지지합니다. 먼저 large-catalog structural retrieval을 고치고 작은 **fixed** shortlist를 사용합니다.

### Evidence sequence

1. Fresh 240-task adaptive DEV surface에서 baseline fixed Top-10 retriever는 registry가 커질수록 저하됐습니다. 100/250/500 endpoints의 Required-route Recall@10은 **97.62% / 96.67% / 87.14%**였습니다.
2. 500-endpoint miss는 equal-score collision과 true below-cutoff ranking error 모두에 집중됐습니다. Post-hoc adaptive-K threshold 변경 대신 structural retrieval successor의 근거가 됐습니다.
3. Fixed structural candidate `STRUCT-4.5-1.5`는 confirmation 전에 freeze했고 independent 240-task surface에서 100/250/500 endpoints 모두 **100% Recall@10 및 100% FullCoverage@10**을 달성했습니다. 모든 supported stratum/language와 typed-unit query를 포함합니다.
4. Unchanged preregistered score-gap adaptive family를 confirmed retriever 위에서 다시 실행했지만 **frozen efficiency gate를 만족한 adaptive policy가 없었고**, threshold retuning 없이 adaptive v3를 종료했습니다.
5. Adaptive candidate가 아니라 control이었던 fixed K=3이 별도 preregistered successor의 근거가 됐습니다. 두 번째 fresh 240-task confirmation에서 `STRUCT-FIXED-3`:
   - required-route Recall: **100.00% / 99.05% / 99.05%**
   - all-required FullCoverage: **100.00% / 98.89% / 98.89%**
   - typed numeric/unit Recall: 100%
   - mean exact SmolLM3 tool-schema tokens: 364.27, fixed K=5는 563.08
   - fixed K=5 대비 mean schema-token reduction: 35.31%
6. 남은 gate는 downstream agent utility입니다. Paired `STRUCT-FIXED-3` vs `STRUCT-FIXED-5` SmolLM3 experiment는 exact canonical B2 surface에 preregistered되어 있으며 canonical B2 run `36642658406`이 **성공적으로** 끝난 뒤에만 launch할 수 있습니다.

Product default는 변하지 않습니다. `structural_retrieval`은 opt-in이고 fixed K=3은 product default가 아니며 broad #432 held-out/final-answer claim은 별도 gate입니다.

Canonical result files:

- 구조 확인 결과 파일: `benchmarks/agent-utility-v5-structural-confirmation-result.json`
- 적응형 v3 결과 파일: `benchmarks/agent-utility-v5-structural-adaptive-v3-result.json`
- 고정 K3 v4 결과 파일: `benchmarks/agent-utility-v5-structural-fixed3-v4-result.json`
- 고정 K3 에이전트 사전등록 파일: `benchmarks/agent-utility-v5-structural-fixed3-agent-preregistration.json`

## Historical protocol

아래는 original adaptive-depth preregistration rationale/selection rule을 보존합니다. Current recommended candidate가 아니라 terminal negative adaptive result를 만든 protocol로 읽어야 합니다.

Tracking issue: #430

질문은 SchemaRouter가 fixed-K baseline의 retrieval coverage/downstream utility를 희생하지 않고 평균 5개 미만 capability를 노출할 수 있는가입니다.

## B1/B2와 분리하는 이유

B1/B2는 fixed shortlist depth를 평가하며 adaptive depth의 tuning data가 아닙니다.

B1/B2 task row, failure, score, per-task outcome은 adaptive rule 선택에 사용할 수 없습니다. Adaptive experiment는 자체 development/confirmation surface를 사용합니다.

## Score semantics

`CapabilityCandidate.score`는 deterministic ranking score이지 backend/catalog 사이 동일 scale이 보장되는 calibrated probability가 아닙니다.

따라서 absolute score threshold를 금지합니다.

유일한 adaptive signal은 ranked Top-10 score range로 normalize한 adjacent gap입니다.

```text
gap_i = (score_i - score_{i+1}) /
        max(score_1 - score_10, 1e-9)
```

이는 `a > 0`인 positive affine transform `score' = a * score + b`에 invariant합니다. Ranking backend가 ordering을 유지하면서 scale/offset을 바꿀 수 있기 때문에 중요합니다. Top-10 score range가 사실상 0이면 rule은 `max_k`로 fail closed합니다.

Evaluated cut position은 rank 3~9입니다.

## Prior-art boundary

Repantis et al., *How Many Tools Should an LLM Agent See? A Chance-Corrected Answer* (arXiv:2605.24660)은 shortlist depth 자체를 evaluation target으로 보고 larger K가 만드는 random chance를 교정하는 Bits-over-Random(BoR)을 도입합니다.

이 cycle은 fixed-K BoR을 diagnostic으로 보고하지만 inference signal, selection criterion, learned depth-policy reward로 사용하지 않습니다. Frozen adaptive candidate는 deterministic score-geometry rule을 유지합니다.

## Frozen candidate policies

Controls: fixed K=3, K=5, K=10.

적응형 후보: REL-GAP-005, REL-GAP-010, REL-GAP-020, MAX-GAP-010.

Learned depth policy는 허용하지 않습니다.

## Development surface

**240 independent semantic tasks**:

- 8 task strata
- 6 languages
- stratum × language cell당 5 tasks

Language policy:

- semantic task마다 정확히 하나의 language cell
- surrounding request grammar는 assigned language
- `Raman peak`, unit, registered operation noun 같은 canonical technical term은 정상 usage면 English 유지 가능
- multilingual request framing의 adaptive shortlist depth를 시험하며 standalone translation quality가 아님
- 같은 DEV task의 cross-language translation을 repeated row로 사용하지 않음

Strata:

1. clear single-tool requests
2. sibling-operation ambiguity
3. semantically adjacent distractors
4. multi-step first-hop selection
5. typed numeric/unit queries
6. read/write siblings
7. near-domain unsupported requests
8. genuine OOD requests

별도 **240-task confirmation surface**는 같은 balance지만 adaptive policy 하나가 선택될 때까지 sealed입니다.

## Development selection

Eligible adaptive policy 조건:

- 100/250/500 각각 required-tool-set Recall >=97%
- 각각 all-required FullCoverage >=97%
- mean exposed candidate count <5
- p95 candidate count <=10
- mean tool-schema tokens < fixed K=5

Eligible 중 frozen lexicographic rule로 정확히 하나 선택:

1. lowest mean candidate count
2. highest required-tool-set Recall
3. highest FullCoverage
4. lowest tool-schema tokens
5. lowest p95 retrieval latency
6. lexicographically smallest policy ID

Post-selection threshold retuning 없음.

## Confirmation과 held-out promotion

Confirmation surface는 tuning eligible이 아닙니다.

Promotion하려면 selected policy가 각 catalog size에서 independently >=97% required-tool coverage/FullCoverage, 평균 <=4.5 candidates, fixed K=5 대비 tool-schema token reduction을 유지하고 B2 terminal 뒤 downstream task pass를 fixed K=5의 2pp 이내로 보존하며 unauthorized destructive execution 0이어야 합니다.

Adaptive condition은 **#432 task content 생성 전에** confirmation gate를 통과한 경우에만 #432에 들어갈 수 있습니다. Held-out content/score가 열린 뒤 추가할 수 없습니다.

## Boundary

Adaptive depth는 candidate exposure만 바꿉니다. Execution authority, validation, approval, policy, tool binding은 바꾸지 않습니다.

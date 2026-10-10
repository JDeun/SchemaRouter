# 0.14 output-field projection과 final-answer quality

Tracking issue: #506

> **현재 상태 — 2026-10-02:** 원래 #506 DEV screen은 frozen small agent가 tool을 호출하지 않았기 때문에 instrument failure로 소비됐습니다. Preregistered #510 successor runtime qualification이 active 상태입니다. 이 과정의 infrastructure recovery는 instrument-transport 작업이지 projection evidence가 아니며, projection successor는 terminal qualified runtime이 나올 때까지 gated 상태입니다.

## 질문

> Query, candidate exposure, selected route, raw tool response를 고정했을 때, **planned declared output field만** 반환하면 final answer의 factual quality가 변하는가? 그리고 agent context를 얼마나 줄이는가?

## 별도 실험이 필요한 이유

SchemaRouter는 raw tool response를 validate한 뒤 plan이 요청한 declared field만 agent에 전달합니다. 이 단계는 구현·배포되어 있으며 [Field-first execution](../concepts/field-first-execution.md)의 core principle로 명시돼 있습니다.

> 목표는 단순히 tool을 선택하는 것이 아닙니다. 사용자의 질문에 답할 수 있는 가장 작은 declared data surface를 식별하는 것입니다.

기존 실험 중 이를 측정하는 것은 없습니다.

| Experiment | 변경하는 것 |
| --- | --- |
| [B1 (#420)](agent-utility-b1-result.md) | agent가 볼 수 있는 tool 수 |
| [#434](typed-capability-retrieval-ablation.md) | retrieval을 위한 capability 표현 방식 |
| [#424](final-answer-quality.md) | catalog-level context reduction에서의 answer quality |
| #506 | 실행된 tool이 반환하는 내용 |

Tool 수를 줄이는 아이디어 자체는 commoditized되어 있습니다. 일반 Top-K tool router와 공유되지 않는 이 설계의 핵심은 field level까지 내려가는 것이며, 지금까지 이에 대한 주장은 evidence가 아니라 argument에 의존했습니다.

## Isolation

모든 condition은 동일한 query, 동일한 candidate exposure(`SR-5`), 동일한 route, 동일한 frozen raw record를 받습니다. Agent에 반환되는 observation만 달라집니다.

| Condition | Agent에 주는 observation |
| --- | --- |
| `RAW-FULL` | validated raw response record 전체 |
| `PROJECTED` | declared planned output field만 |
| `PROJECTED+CONTRACT` | planned field + declared `semantic_id` / unit / qualifier |
| `ORACLE-MINIMAL` | gold answer에 필요한 field만 |

Transform은 agent context에만 적용됩니다. Executor 자체 record, task state, 모든 completion check는 untransformed observation을 계속 보기 때문에 presentation이 ground truth를 움직일 수 없습니다. 이 속성은 주장만 하는 것이 아니라 test로 고정합니다.

`ORACLE-MINIMAL`도 필요합니다. B1에서 `ORACLE`이 `SR-5`를 지배하지 않았으므로 over-minimizing은 strawman이 아니라 실제 가설입니다.

## Corpus

144 semantic task: 6 projection strata × 6 languages × 4 independent tasks. Catalog size 100과 250은 task 내부에 nested된 repeated measure입니다.

| Stratum | Raw record에 배치하는 competing content |
| --- | --- |
| `qualifier_sibling` | 다른 declared temperature의 동일 quantity |
| `unit_variant` | GPa와 함께 MPa/psi로 표시된 동일 quantity |
| `superseded_duplicate` | current value의 legacy/draft revision |
| `nested_record` | audit record 아래 nested된 computed value |
| `cross_provider_name_collision` | generic `value` / `result` key와 두 번째 provider의 copy |
| `multi_step_provenance` | 두 step에 걸친 staging/cache/temp/mirror URI |

Raw record가 declared plan 이외의 내용을 전혀 포함하지 않으면 corpus validation은 **fail closed**합니다. Competing content가 없으면 `RAW-FULL`과 `PROJECTED`가 동일한 observation이 되어 비교할 것이 없어집니다. Projection 이후 required fact에 접근할 수 없는 task도 validation에서 거부합니다. 그렇지 않으면 `PROJECTED`가 실제로 보지 못한 evidence를 기준으로 scoring될 수 있기 때문입니다.

## Metrics

이슈 #424의 규칙에 따라 각각 별도로 보고하며 하나의 score로 합치지 않습니다.

- required-fact recall
- numeric value accuracy
- unit accuracy
- provenance accuracy
- unsupported-fact rate
- contradiction count
- exact mandatory-field completion
- observation characters 및 total input tokens
- turns, wall latency
- unauthorized destructive executions

Statistical unit은 semantic task입니다. Catalog repeat는 resampling 전에 task 내부에서 평균하므로 sample 수를 부풀릴 수 없습니다. `RAW-FULL` 대비 delta는 task 내부 paired comparison으로 계산하고 10,000-iteration cluster bootstrap 95%로 보고합니다.

## Promotion gate

Quality non-inferiority와 observation context의 strict reduction을 모두 요구합니다.

| Requirement | `RAW-FULL` 대비 threshold |
| --- | ---: |
| required-fact recall | ≥ −2pp |
| numeric value accuracy | ≥ −2pp |
| unit accuracy | ≥ −2pp |
| provenance accuracy | ≥ −2pp |
| unsupported-fact rate | ≤ +1pp |
| contradiction count | 증가하지 않음 |
| unauthorized destructive executions | 0 |
| observation characters | strictly lower |

Quality *gain*은 보고할 수 있지만 필수는 아닙니다. Context reduction만으로는 통과하지 않습니다.

## Staging

두 arm 모두 0.14 conveyor가 구동하며 manual dispatch가 필요하지 않습니다.

1. **Development screen** — frozen B1 small agent
   (`Qwen/Qwen3-0.6B` @ `c1899de2`). 정확히 동일한 published B1 runtime을 재사용하여 새로운 미특성화 model을 도입하지 않고 context measurement의 비교 가능성을 유지합니다.

   Upstream artifact를 소비하지 않으므로 conveyor는 이를 **B2 gate 이전에** 진행합니다. Frozen chain 뒤에 queue하면 과학적 이유 없이 development evidence가 지연되고 controller의 early return 때문에 starvation될 수 있습니다.

2. **Confirmation** — canonical strong agent
   (`HuggingFaceTB/SmolLM3-3B` @ `a07cc9a0`), conveyor의 **terminal-evidence stage 이후에 append**되며 terminal digest를 key로 사용합니다.

   Insert가 아니라 append하는 것이 중요합니다. Conveyor DAG는 downstream corpus generation 전에 preregister되어 이미 실행 중입니다. Stage를 삽입하면 기존 stage input/order가 이동하지만 terminal evidence 뒤에 append하면 그렇지 않습니다. Amendment와 변경하지 않은 항목 목록은 `benchmarks/agent-utility-0.14-conveyor-preregistration.json`에 기록돼 있습니다.

   Workflow는 B2 outcome을 읽지 않고 canonical B2 run의 성공 여부만 확인합니다.

### Source freeze

이슈 #506은 **자체 frozen implementation revision**을 갖습니다. 첫 dispatch에서 resolve하고 실제 experiment script가 포함돼 있는지 확인한 뒤 두 arm이 동일 revision을 재사용합니다.

이는 절대 `DOWNSTREAM_IMPLEMENTATION_SHA`가 아닙니다. 해당 SHA는 이미 frozen된 #431/#432/#424 chain에 속하며 모든 projection script보다 오래됐습니다. 따라서 그 revision으로 dispatch하면 experiment를 실행할 파일이 없는 tree를 checkout하게 됩니다. Unit test는 실제 checkout이 아닌 stub을 사용하므로 이 문제가 green 상태에서도 숨어 있었습니다. 현재 두 workflow는 preflight에서 이런 checkout을 거부하고 controller도 필요한 file이 없는 revision dispatch를 거부합니다.

### Development vs confirmation

두 arm은 동일한 frozen corpus, generator, condition, scorer를 사용하므로 development screen은 **diagnostic only**입니다. Scoring이 시작된 이후 결과를 이용해 다음을 변경할 수 없습니다.

- conditions
- task wording/content
- distractor strata
- threshold/promotion gate
- scorer
- prompt/harness semantics
- row inclusion
- frozen projection source

Confirmation에서 달라질 수 있는 preregistered 요소는 runtime 하나뿐입니다. 이는 B1과 B2의 관계와 같습니다. 하나의 frozen protocol, 더 강한 agent입니다.

Screen 결과를 보고 design change가 필요하다면 이 experiment를 consumed 상태로 닫고 query-disjoint surface를 가진 successor를 새로 preregister해야 합니다. 현재 experiment를 수정해서는 안 됩니다.

Development screen은 run `36682589574`에서 null result를 반환했습니다. Frozen B1 agent가 tool을 한 번도 호출하지 않았기 때문에 projection이 영향을 줄 대상 자체가 없었습니다. 이 screen은 consumed 상태입니다. Frozen capability gate로 instrument를 선택하고 자체 query-disjoint surface를 갖는 replacement는 [successor screen](successor-screen.md)입니다. Confirmation arm은 영향을 받지 않습니다.

## Independence

- fresh disjoint task surface
- B1 row는 tuning data가 아님
- #432 held-out row는 tuning data가 아님
- sealed #424 corpus를 사용하지 않으며 여기의 결과로 #424를 tune할 수 없음
- B1에 retrofit하지 않음

## Claim boundary

Gate가 통과하면 허용되는 주장은 frozen surface 범위로 제한됩니다.

> 평가된 surface에서 planned declared field만 반환해도 final-answer factual quality를 보존하면서 agent observation context를 줄였습니다.

이는 population-level generalization을 입증하지 않습니다. 그 역할은 [#432](large-heldout-agent-utility.md)에 남습니다.

## Reproduction

```bash
python scripts/generate_agent_utility_v7_projection_corpus.py \
  --source-revision "$(git rev-parse HEAD)" \
  --out artifacts/projection/projection-corpus.json

python scripts/validate_agent_utility_v7_projection_corpus.py \
  --corpus artifacts/projection/projection-corpus.json
```

Preregistration: `benchmarks/agent-utility-v7-field-projection-preregistration.json`.

# 0.14 output-field projection successor development screen

Tracking issue: #510

## 존재 이유

[output-field projection](field-projection-answer-quality.md) development screen은 null result였습니다. Comparator 포함 모든 condition에서 factual metric이 0.0000이었습니다. 가설 때문이 아닙니다. Shard row에서 `tool_call_count = 0`, mean `turns = 1.21`이었고 frozen B1 agent가 tool use를 건너뛰고 tool 이름에서 answer envelope를 fabricate했습니다.

더 좁혀 보면 B1은 같은 runtime/harness에서 `SYSTEM_PROMPT`로 68–91% task pass를 달성했습니다. Projection screen은 structured answer envelope를 추가로 요구하는 `FINAL_SYSTEM_PROMPT`를 사용합니다.

> Qwen3-0.6B는 tool-calling **또는** structured answer envelope는 할 수 있지만 둘을 동시에 하지 못합니다.

Prompt를 완화하고 같은 corpus를 재실행하는 것은 #506 Option A governance가 금지합니다. `prompt or harness semantics`가 frozen list에 있기 때문입니다. 허용된 path는 screen을 consumed로 닫고 자체 query-disjoint surface의 successor를 preregister하는 것입니다.

## Instrument eligibility

Candidate를 실행하기 **전에** freeze한 gate로 instrument를 선택합니다. Roster를 실행하고 best performer를 고르면 outcome으로 instrument를 선택하는 동일 오류가 한 단계 위에서 반복됩니다.

| Criterion | Threshold |
| --- | ---: |
| valid answer envelope episode | ≥ 80% |
| 최소 한 번 tool call episode | ≥ 90% |
| 최소 하나 observation-grounded fact 포함 episode | ≥ 70% |

세 번째 criterion은 tool을 호출하면서도 grounding을 전혀 하지 않는 runtime을 잡습니다.

Frozen ordered roster:

1. `HuggingFaceTB/SmolLM3-3B`
2. `Qwen/Qwen3-4B`
3. `Qwen/Qwen3-8B`

Exact revisions:

- `HuggingFaceTB/SmolLM3-3B@a07cc9a04f16550a088caea529712d1d335b0ac1`
- `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`
- `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`

모든 candidate는 CPU bfloat16 on `ubuntu-24.04-arm`, Python 3.12.14, PyTorch 2.14.0+cpu, Transformers 4.57.6입니다. SmolLM3는 canonical SDPA + `xml_tools`, Qwen은 earlier Qwen development agent와 같은 OpenAI-function-tool chat-template semantics를 사용합니다. 이는 experiment outcome이 아니라 instrument definition입니다.

**첫 번째** qualifying candidate를 사용하며 이후 candidate는 실행하지 않습니다. Qualifier 중 선택하면 outcome-based selection이 됩니다.

`select_runtime` in `scripts/qualify_agent_utility_runtime.py`가 public selection boundary입니다. Bare rate dictionary를 받지 않습니다. 모든 candidate는 frozen qualification corpus에 연결된 provenance-bearing evidence를 제공해야 하며 evidence class, surface identity, exact corpus task hash, exact source/harness revision, pinned model revision, exact episode count, complete frozen task-ID set을 검증한 뒤 ordered-roster rule을 적용합니다.

Qualification은 자체 frozen surface를 가집니다. `scripts/generate_agent_utility_v8_qualification_corpus.py`가 projection-stratum/language pair마다 한 task, 총 36 episodes를 생성하며 `SR-5`와 `RAW-FULL`로 고정합니다. #506/successor screen과 exact query string을 공유하지 않습니다. Artifact는 instrument evidence일 뿐 projection evidence가 아닙니다.

Workflow는 `.github/workflows/research-0.14-runtime-qualification.yml`입니다. Candidate execution 전에 corpus를 generate/validate하고 exact candidate revision 및 frozen source/harness identity를 기록하며 complete provenance-bearing evidence를 `select_runtime`에 전달합니다. Ad-hoc row나 rate comparison 재구현은 invalid입니다.

### Current qualification execution status — 2026-10-02

Infrastructure failure는 frozen roster를 advance하지 않습니다.

- run `36710813766`: qualification corpus artifact double-nested path로 inference 전 실패
- run `36808991480`: later Qwen3-8B shard evaluator cache-availability failure 재현
- recovery-2 `36897572955`: fail-closed evaluator cache restore로 affected Qwen3-8B shard가 inference 전 종료
- PR #656이 shared-cache availability를 scientific prerequisite에서 제거하면서 exact `QUAL_MODEL@QUAL_REV` pin을 보존했고 merge `290f02355570a7db637413d7421fb648f26497b8`가 recovery-3 run `36922946442`를 자동 launch

Recovery-3는 동일 frozen qualification contract의 infrastructure-only continuation입니다. Invalid attempt의 partial row는 model-quality evidence가 아니며 ordered selector가 required roster prefix의 complete evidence를 받기 전 candidate를 선택할 수 없습니다.

### Recorded trade-off

`SmolLM3-3B`는 confirmation arm runtime이기도 하므로 screen/confirmation 차이는 surface뿐입니다. 이 trade-off는 수용합니다. B2 canonical run이 이 model의 tool-calling 수행을 이미 보여 첫 qualifier일 가능성이 가장 높고 qualify할 수 없는 screen은 가치가 없습니다. Screen surface는 query-disjoint라 confirmation surface를 소비하지 않습니다.

## #506과 동일한 것

Four conditions, six distractor strata, six languages, separately reported metrics, paired cluster bootstrap, promotion gate는 unchanged입니다. **runtime**과 **surface**만 다릅니다.

## Query disjointness

Test에 맡기지 않고 generation에서 강제합니다. `build_corpus`는 prior surface와 normalized query를 공유하면 write 전에 raise합니다. #506 projection corpus는 generator 내부에서 local build해 직접 검사하며 `scripts/agent_utility_prior_query_guard.py`에는 등록하지 않습니다. 등록하면 `known_prior_query_manifest()["union_sha256"]`가 바뀌어 기존 v3/v4/v6 corpus validator와 충돌하기 때문에 local check를 사용합니다.

여기서 "disjoint"의 정확한 의미: 이 surface는 #506 corpus에서 identifier space만 `P####` → `S####`로 바꾼 것입니다. Prefix 외 task content는 byte-identical입니다. Disjointness는 *query string 미공유*만 의미하며 content-independent surface는 아닙니다. #506 screen이 tool을 호출하지 않아 observation content가 model에 도달하지 않았고 prior run으로 training하지 않으므로 acceptable로 판단했습니다. #510의 "not one query shared"는 충족하지만 surface가 genuinely different content라는 뜻은 아닙니다.

## Governance

Screen은 development evidence입니다. Confirmation으로 보고할 수 없고 condition, task content, distractor strata, threshold, scorer, prompt/harness semantics, row inclusion을 바꿀 수 없습니다. #506 corpus/condition/gate/confirmation arm은 untouched입니다.

Candidate가 하나도 qualify하지 않으면 screening approach에 대한 terminal result로 기록합니다. Threshold를 약화할 이유가 아닙니다.

Workflow는 roster order를 엄격히 지킵니다. Later candidate는 previous candidate가 complete measured evidence를 내고 frozen threshold를 실패한 뒤에만 시작합니다. Cache failure, runner OOM, model-load failure, missing shard, workflow failure 같은 infrastructure failure는 scientific non-qualification이 아니며 chain을 중단합니다. Final selector는 incomplete failed prefix를 거부합니다.

## Reproduction

Qualification surface:

```bash
python scripts/generate_agent_utility_v8_qualification_corpus.py \
  --source-revision "$(git rev-parse HEAD)" \
  --out artifacts/successor/qualification-corpus.json

python scripts/validate_agent_utility_v8_qualification_corpus.py \
  --corpus artifacts/successor/qualification-corpus.json
```

Successor development surface:

```bash
python scripts/generate_agent_utility_v8_successor_corpus.py \
  --source-revision "$(git rev-parse HEAD)" \
  --out artifacts/successor/successor-corpus.json

python scripts/validate_agent_utility_v8_successor_corpus.py \
  --corpus artifacts/successor/successor-corpus.json
```

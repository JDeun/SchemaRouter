# 의사결정 라우팅 벤치마크

SchemaRouter는 재현 가능한 라우팅 벤치마크 실행 도구와 저장소에 포함된 v1 코퍼스를 제공합니다.

이 벤치마크는 성능을 측정하기 위한 도구이며, 특정 제공자가 모든 상황에서 우수하다는 주장은 아닙니다.

## 간단 검증 실행

```bash
python scripts/benchmark_decision_routing.py
```

이 명령은 패키징과 CI를 검증하는 기존의 결정론적 3개 사례 테스트를 그대로 실행합니다.

## 저장소에 포함된 전체 코퍼스

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json
```

v1 코퍼스는 다음 범주의 144개 사례로 구성됩니다:

- 일반적인 라우팅 요청;
- 이름이나 기능이 매우 유사한 도구·엔드포인트;
- 한국어·영어 다국어 질의;
- 드물게 사용되는 표현;
- 프롬프트 인젝션을 시도하는 요청;
- 제한된 선택지만 처리하는 백엔드가 경로 선택을 보류할 수 있는 도메인 외 요청.

이 코퍼스는 스크립트에 내장된 안정적인 벤치마크 레지스트리만 참조합니다. 테스트는 등록되지 않은 예상 경로가 데이터셋에 유입되지 않도록 검증합니다.

### v2 부하 테스트 코퍼스와 홀드아웃 데이터 분할

`benchmarks/decision-routing-v2.json`은 deterministic한 **1,200-case** multilingual stress corpus입니다:

- 등록된 경로 16개 × 경로당 60개 사례 = **in-domain 960개**
- 명시적인 경로 없음(no-route) / 도메인 밖(OOD) 사례 **240개**
- 언어: 영어, 한국어, 스페인어, 일본어, 독일어, 한국어·영어 혼합
- 고정 데이터 분할: `dev` 720개, `calibration` 240개, `test` 240개

corpus는 `scripts/generate_decision_routing_v2.py`로 재생성하며 test는 생성 결과가 checked-in JSON과 정확히 일치하도록 요구합니다. 이는 template-derived stress corpus이며 독립적으로 수집한 실제 human traffic을 대체하지 않습니다.

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v2.json \
  --split calibration
```

recall width와 confidence threshold는 `dev` / `calibration`에서만 조정합니다. configuration이 고정될 때까지 `test`는 held-out으로 취급합니다. v2 test split은 semantic-recall checkpoint에서 이미 한 번 사용됐으므로 이제 tuning set이 아니라 frozen regression set입니다.

### v3 평가 전까지 미사용한 기능 적합성 홀드아웃

`benchmarks/decision-routing-v3.json`은 capability-fit 실험을 위한 별도의 deterministic **600-case** multilingual holdout입니다:

- 등록된 경로 16개 × 경로당 30개 = **in-domain 480개**
- 명시적 경로 없음 / OOD 사례 **120개**
- 영어, 한국어, 스페인어, 일본어, 독일어, 한국어·영어 혼합 언어를 각각 **100개 사례**씩 포함
- 모든 사례를 `test`로 표시
- v2와 정규화된 질의가 정확하게 겹치는 사례 없음

corpus는 `scripts/generate_decision_routing_v3.py`로 재현 가능하게 생성됩니다. capability-fit threshold는 v2 `dev` / `calibration`에서만 조정하고 선택한 threshold를 고정한 뒤 v3를 정확히 한 번 평가합니다. 첫 평가 이후 v3 역시 frozen regression set이 됩니다.


## 결과 저장

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --repeat 3 \
  --json-out artifacts/decision-benchmark.json \
  --csv-out artifacts/decision-benchmark.csv \
  --html-out artifacts/decision-benchmark.html
```

주요 control:

- `--max-cases N`: 제한된 로컬 샘플에 대한 실행
- `--repeat N`: 지연 시간을 반복 측정
- JSON 출력: 집계 및 보고 자동화
- CSV 출력: 행 수준 분석
- 자체 포함 HTML 출력: 이식 가능한 백엔드·지연·기권 현황 요약

HTML 파일은 remote asset/script를 포함하지 않고 rendering 전에 report metadata를 escape합니다. 재현 가능한 단일 run summary 공유를 위한 형식입니다.

날짜별 benchmark JSON 파일 묶음은 raw measurement를 다시 쓰지 않고 comparison view로 rendering할 수 있습니다:

```bash
python scripts/render_benchmark_history.py \
  artifacts/run-2026-09-23.json \
  artifacts/run-2026-09-30.json \
  --output artifacts/decision-benchmark-history.html
```

history renderer는 각 run의 timestamp, SchemaRouter version, exact source revision, corpus SHA-256, corpus path, hardware, backend, accuracy, abstention, latency, model, device metadata를 보존합니다. 서로 다른 environment를 normalize하지 않으므로 cross-run comparison은 measurement condition이 동등할 때만 유효합니다.

## ModelQueryAnalyzer

`module:function` syntax로 provider callable을 전달합니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --model-callable my_bench_provider:analyze
```

callable은 `ModelQueryAnalyzer`와 동일한 structured request를 받으며 sync/async 모두 가능합니다. 따라서 benchmark는 provider-neutral하게 유지됩니다.

## 임의 bounded decision callable

Jev/System One wire protocol을 노출하지 않는 typed decision model은 runtime을 일반 SchemaRouter bounded decision callable로 감싸 명시적으로 load합니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --decision-callable my_decision_provider:decide \
  --decision-callable-name anyjev-local
```

callable은 `DecisionRequest`를 받아 `DecisionResult` 또는 동등한 mapping을 반환합니다. SchemaRouter는 이를 `CallableDecisionBackend`로 감싸고 반환된 모든 option ID를 제공된 유한 집합에 대해 검증합니다.

이는 실험적인 AnyJev/Nimble adapter처럼 wire-compatible하지 않은 System One 계열 runtime을 위한 권장 research seam입니다. 새로운 model family를 benchmark하기 위해 영구적인 core integration을 추가하는 일을 피할 수 있습니다.

callable은 명시적으로 지정한 trusted local Python code입니다. SchemaRouter는 임의의 설치 decision provider를 auto-discover하거나 auto-import하지 않습니다.

## Embedding backend

`module:function` syntax로 batch embedding callable을 전달합니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --embedding-callable my_embeddings:embed_batch \
  --min-similarity 0.35 \
  --min-margin 0.05
```

callable은 query와 제공 option별 text representation이 이어지는 list를 받고 input마다 vector 하나를 반환합니다. sync/async 모두 가능하며 SchemaRouter가 cosine ranking을 local에서 수행하므로 benchmark contract를 바꾸지 않고 FastEmbed, SentenceTransformers, semantic-router encoder, application-specific embedding service를 비교할 수 있습니다.

threshold 값은 workload/model별로 다릅니다. 다른 embedding model에서 측정한 threshold를 recalibration 없이 재사용하지 않습니다.

### Final decision 전 semantic top-k recall

동일한 embedding contract를 candidate recall에만 사용하고 Laya, Jev, Ollama 또는 hosted bounded backend가 final selection을 수행하게 할 수 있습니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v2.json \
  --split calibration \
  --laya \
  --candidate-recall-embedding-callable benchmarks.multilingual_embedder:embed \
  --candidate-recall-limit 4
```

Control:

- `--candidate-recall-embedding-callable module:function`;
- `--candidate-recall-limit N`;
- `--candidate-recall-min-similarity FLOAT`;
- `--candidate-recall-min-margin FLOAT`.

checked-in research callable은 benchmark environment에서만 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`를 사용하며 `sentence-transformers`는 SchemaRouter package dependency가 아닙니다.

Research Benchmark는 먼저 calibration split에서 recall width를 비교하고 confidence threshold를 offline sweep합니다. held-out test split은 configuration 선택 후에만 평가합니다.

## Generic System One-compatible provider

hosted/self-hosted runtime이 Jev-compatible `/v1/systemone` contract를 제공하면 model-neutral System One backend를 사용합니다. 별도 backend 구현 없이 동일 benchmark에서 Kev 또는 향후 compatible decision model을 비교할 수 있습니다.

neutral extra를 설치합니다:

```bash
pip install -e ".[systemone]"
```

local Kev-style server 예제:

```bash
export SYSTEM_ONE_API_KEY="local"
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --system-one-base-url http://127.0.0.1:8009 \
  --system-one-provider kev-local \
  --system-one-model kev-latest \
  --system-one-min-confidence 0.70
```

사용 가능한 control:

- `--system-one-base-url URL`: 범용 호환 백엔드 활성화
- `--system-one-model MODEL`: 공급자 모델·체크포인트 별칭 고정
- `--system-one-provider NAME`: 데이터 행 및 보고서에 안정적인 공급자 라벨 기록
- `--system-one-timeout SECONDS`: 요청 시간 초과 설정
- `--system-one-min-confidence FLOAT`: 최소 신뢰도 설정
- `--system-one-api-key-env NAME`: 자격 증명을 담은 환경 변수 지정

credential 값은 benchmark output에 기록하지 않습니다. report에는 key 설정 여부와 reproducibility에 필요한 non-secret provider/model/base-URL/runtime configuration만 기록합니다.

wire compatibility 자체는 품질 주장이 아닙니다. model/checkpoint/runtime을 변경할 때 confidence는 development/calibration evidence에서만 재보정하고, 고정된 configuration을 untouched holdout에서 평가합니다.

## Jev

optional integration을 설치하고 TypeSafe를 로컬에서 설정합니다:

```bash
pip install -e ".[jev]"
export TYPESAFE_API_KEY="..."
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --jev
```

optional control에는 `--jev-model`, `--min-confidence`, `--input-cost-per-million`, `--output-cost-per-million`이 있습니다.

provider pricing은 SchemaRouter와 무관하게 변경될 수 있으므로 hard-code하지 않습니다.

## Laya

optional local decision runtime을 설치합니다:

```bash
pip install -e ".[laya]"
```

동일한 checked-in corpus에서 Laya를 실행합니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya
```

기본적으로 Laya는 local router를 사용해 bounded request state에서 English 또는 multilingual checkpoint를 선택합니다. optional control은 다음과 같습니다:

- `--laya-model english|multilingual|typed-decisions`: 체크포인트 고정
- `--laya-device cpu|cuda|mps`: 신뢰된 로컬 장치 고정
- `--laya-preload`: 측정 전에 체크포인트 미리 로드
- `--laya-max-loaded N`: 상주하는 체크포인트 수 제한
- `--laya-min-confidence FLOAT`: 신뢰도 게이트에 따른 기권 측정
- `--hardware-label TEXT`: 실제 기기·GPU 설명을 보고서에 기록
- `--source-revision TEXT`: CI가 제공하지 않을 때 정확한 코드 리비전 기록
- `--decision-recall-on-empty`: 어휘 기반 후보 검색이 비었을 때 활성화된 제한형 의사결정 백엔드가 등록된 엔드포인트 카탈로그를 검사하도록 명시적으로 허용
- `--candidate-abstention inherit|deterministic|no_route|error`: 백엔드의 명시적인 기권을 공급자 오류 시 폴백과 구분

Laya row는 routed checkpoint와 `requested_device`, decision confidence를 기록하고 Laya가 loaded agent device를 노출하면 `actual_device`도 기록합니다. 사용할 수 없는 CUDA/MPS target이 CPU로 fallback될 수 있으므로 이를 accelerator result로 계산해서는 안 됩니다.

empty-candidate recall은 기본적으로 꺼져 있습니다. 활성화해도 SchemaRouter는 route를 임의 생성하지 않고 trusted local catalog에 이미 등록된 endpoint만 노출합니다. 확장 후 backend가 error/abstain하면 fallback할 lexical candidate가 없으므로 임의 deterministic route 없이 planning이 fail-closed됩니다. model-driven no-route 동작이 필요한 workload에서는 confidence gating과 `candidate_abstention="no_route"`를 함께 사용하고 representative data에서 threshold를 calibration합니다.

zero-threshold run은 model inference를 반복하지 않고 offline에서 recalibration할 수 있습니다:

```bash
python scripts/calibrate_decision_threshold.py \
  artifacts/laya/recall-on-empty/report.json \
  --backend laya:auto \
  --json-out artifacts/laya/calibration.json \
  --csv-out artifacts/laya/calibration.csv \
  --html-out artifacts/laya/calibration.html
```

calibration은 low-confidence case를 기록된 deterministic fallback route 또는 `--abstention-mode no_route`의 최종 no-route result로 replay할 수 있습니다. threshold 0.00~0.95에 대해 overall/category accuracy, confidence coverage, backend abstention, final no-route rate, expected no-route recall, expanded-candidate selection rate를 보고합니다. 이를 통해 threshold tuning을 model/runtime latency와 분리하고 반복 inference 비용을 피합니다.

Laya가 활성화되면 Benchmark JSON은 설치된 Laya, PyTorch, Transformers package version도 기록해 날짜별 결과를 실제 local runtime 기준으로 재현할 수 있게 합니다.

mixed-language latency 측정에서는 **cold-swap**과 **steady-state resident** condition을 구분합니다. auto language routing에서 `max_loaded=1`이면 corpus가 language를 번갈아 사용할 때 English/multilingual checkpoint가 반복 evict될 수 있습니다. 따라서 checked-in Research Benchmark는 `--laya-max-loaded 2 --laya-preload`를 사용합니다. timed per-case loop 전에 두 language checkpoint를 모두 load하고 memory가 허용하면 resident 상태로 유지합니다. constrained-memory checkpoint churn을 측정할 때만 `max_loaded=1`을 사용합니다.

공개 결과에는 exact Laya package version, checkpoint/routing policy, hardware, device, preload policy, confidence threshold, source revision, corpus SHA-256, repeated-run count를 기록해야 합니다. benchmark report는 가능한 경우 이 reproducibility field를 직접 기록합니다. prompt, option, corpus, measurement condition이 동등하지 않다면 upstream/provider benchmark 수치를 직접 비교하지 않습니다.

## Ollama

이미 설치된 local Ollama model을 동일 corpus에서 실행합니다:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --ollama-model your-installed-model
```

기본 API endpoint는 `http://127.0.0.1:11434`입니다. 다른 trusted endpoint에는 `--ollama-base-url`, request별 timeout 조정에는 `--ollama-timeout`을 사용합니다. server가 지원하는 local runtime option은 vendor/version-specific knob를 hard-code하지 않고 전달할 수 있습니다:

```bash
python scripts/benchmark_decision_routing.py \
  --ollama-model your-installed-model \
  --ollama-options-json '{"your_runtime_option": 1}' \
  --hardware-label "RTX workstation"
```

SchemaRouter는 options object를 benchmark report에 기록합니다. 실제 Ollama CPU/GPU placement는 Ollama server/runtime의 결정이므로 추론하지 않습니다.

server가 제공하면 benchmark는 Ollama prompt/evaluation token counter를 기록합니다. local model evidence를 공개할 때는 exact model tag뿐 아니라 quantization/runtime configuration, hardware, Ollama version도 기록해야 합니다. model tag만으로는 local latency나 quality를 재현할 수 없습니다.

operator가 local cost model을 명시적으로 부여하지 않는 한 순수 local Ollama run에는 provider pricing이 무관합니다.

## 측정 지표

각 row에는 다음을 기록합니다:

- 사례 ID, 분류, 고정된 데이터 분할, 언어 레이블
- 보고된 경우 provider/model identifier
- backend가 보고할 수 있는 경우 requested/actual local device
- expected/predicted `tool.endpoint`
- correctness
- invalid-plan state
- end-to-end planning latency
- bounded decision backend 실제 호출 여부
- empty lexical recall을 registered catalog로 명시적으로 확장했는지 여부
- bounded-backend abstention과 deterministic fallback state
- 보고된 경우 input/output token
- optional cost estimate
- provider/planner error

aggregate report에는 다음이 포함됩니다:

- final-plan routing accuracy와 95% Wilson score interval(abstention case는 final plan에 route가 없을 때만 correct)
- invalid-plan rate
- error count
- bounded-backend invocation count/rate
- final expected no-route recall과 95% Wilson score interval
- abstention rate
- final-plan accuracy와 별도로 보고하는 bounded backend expected-abstention recall
- fallback count
- mean, p50, p95 latency
- category-level accuracy와 category별 95% Wilson score interval
- split-level/language-level accuracy
- token total과 optional estimated cost

## Offline evidence와 live evidence

corpus와 deterministic smoke path는 external provider가 필요하지 않으므로 CI에 적합합니다.

live provider benchmark는 별도로 유지합니다. network availability, model revision, credential, rate limit, provider-side change, local accelerator availability, memory, runtime placement는 외부 변수입니다. live 결과를 공개할 때는 정확한 날짜, model identifier, configuration, corpus revision, repeated-run count를 함께 기록합니다.

보고된 95% Wilson interval은 checked-in corpus의 binomial sampling uncertainty를 정량화합니다. model/provider drift, correlated repeated case, hardware variance, distribution shift는 반영하지 않습니다. 3-case smoke set이나 단일 live run으로 provider 우위를 추론해서는 안 됩니다.


## Operation-capability fit protocol

near-domain unsupported operation은 일반 out-of-domain traffic과 분리해 평가합니다.
v5 operation corpus는 576개 multilingual case로 구성됩니다. supported route operation 288개와 near-domain unsupported operation 288개이며 development 384개, calibration 192개로 나뉩니다.

operation-fit threshold는 v5 development/calibration result만으로 선택해야 합니다. 600-case v6 operation holdout은 supported route 384개, near-domain unsupported-operation negative 192개, ordinary out-of-domain negative 24개로 구성되며 language group별 100개로 균형화되어 있습니다. v6는 이전 operation-fit input representation으로 이미 평가되었으므로 regression evidence일 뿐 새로운 untouched generalization claim에 재사용할 수 없습니다.

protected GitHub Actions holdout job은 현재 v9를 대상으로 하며 manual-only입니다. pull-request run과 일반 manual benchmark run에서는 skip됩니다. v6와 v7은 consumed regression evidence이고 v8은 calibration diagnostic path에서 실수로 소비되어 untouched claim을 지원할 수 없습니다. v9는 alias-aware operation-fit implementation 평가 전에 예약되었습니다. alias-aware v5 threshold를 0.40으로 고정한 뒤 v9는 2026-09-26 정확히 한 번 소비되었습니다. permanent workflow guard는 manual/threshold-gated 상태를 유지해 consumed corpus가 fresh holdout으로 조용히 제시되는 것을 방지합니다.

이 실험에서 고정한 upstream stack은 다음과 같습니다:

- semantic candidate recall top-k = 2;
- broad capability-fit min similarity = 0.25;
- 동일 도구 내 엔드포인트 구분 최소 마진 = 0.03.

v5 calibration에서는 operation-fit threshold만 변경합니다. label-cleaned operation-fit surface에서는 v7 평가 전에 threshold를 고정하고 v7 result로 재조정하지 않습니다.

label-cleaned surface에서는 v7 평가 전에 v5의 0.05~0.70 sweep으로 `operation_fit_min_similarity = 0.45`를 고정했습니다. selection rule은 calibration accuracy 최대화이며 dev accuracy는 stability check로 사용합니다. 0.45에서 calibration accuracy 65.625%, dev accuracy 66.667%였고 인접 threshold 0.40과 0.50은 각각 calibration accuracy 60.938%, 60.417%였습니다. 이 고정값을 v7 결과에 따라 변경해서는 안 됩니다.

고정된 0.45 threshold에서 one-shot v7 평가는 overall accuracy 46.833%(95% Wilson CI 42.873%–50.834%), supported operation routed accuracy 28.646%(24.353%–33.362%), near-domain unsupported operation accuracy 76.562%(70.086%–81.997%), ordinary out-of-domain accuracy 100%를 기록했습니다. 이는 threshold 재조정 대상이 아니라 distribution-shift diagnostic으로 취급합니다. v7 holdout은 이미 소비되었고 workflow guard는 manual-only로 복원되었습니다.

후속 trusted-alias surface에서는 development/calibration만 사용한 post-alias v5 sweep으로 `operation_fit_min_similarity = 0.40`을 고정했습니다. 이 threshold에서 one-shot v9 평가는 overall accuracy 51.167%(95% Wilson CI 47.172%–55.146%), supported alias-operation routed accuracy 38.281%(33.558%–43.236%), near-domain unsupported operation accuracy 70.833%(64.046%–76.804%), ordinary out-of-domain accuracy 100%(86.202%–100%)를 기록했습니다. language-group accuracy는 Korean 40%에서 Japanese 57%까지였습니다. 이 결과는 untouched generalization evidence로 보존합니다. alias는 consumed v7 diagnostic 대비 supported-route surface를 개선했지만 operation selection recall은 unsupported-operation rejection보다 여전히 상당히 약합니다. v9는 이제 consumed 상태이며 threshold retuning에 사용할 수 없습니다.


### Post-v9 concise surface와 v10 generalization holdout

v9 one-shot 결과 이후 stage-attributed v5 dev/calibration profiling에서 operation-fit abstention이 여전히 dominant supported-route suppression stage임을 확인했습니다. 이미 고정된 0.40 threshold에서 **v5 development/calibration만 사용해** 세 representation variant를 비교했습니다:

- concise endpoint name + trusted alias + endpoint description: endpoint disambiguation 이후 dev/calibration 모두 balanced operation score 69.792%
- 반복 natural-language `Supported operation:` phrase: dev 64.062% / calibration 63.542%
- 별칭별 최대값을 독립적으로 취하는 변형: 개발 집합 59.635% / 보정 집합 60.417%

concise representation은 v10을 확인하기 전에 선택했습니다. 이후 0.05~0.70의 새 threshold sweep 역시 v5 dev/calibration만 사용했습니다. robustness score는 dev와 calibration balanced operation score 중 더 낮은 값입니다. 선택 threshold는 `operation_fit_min_similarity = 0.40`으로 유지되었습니다. 0.35는 67.188%, 0.40은 69.792%, 0.45는 67.708% robustness를 기록했습니다.

`benchmarks/decision-routing-v10-operation-generalization-holdout.json`은 이 representation optimization 전에 고정한 600-case six-language test-only generalization corpus입니다. supported operation 384개, near-domain unsupported operation 192개, ordinary out-of-domain request 24개를 포함합니다.

representation과 threshold를 고정한 뒤 v10은 2026-09-26 semantic recall top-k 2, capability-fit 0.25, operation-fit 0.40, endpoint-disambiguation margin 0.03으로 정확히 한 번 평가했습니다. 최종 stack 결과는 다음과 같습니다:

- overall accuracy 55.667%(95% Wilson CI 51.668%–59.593%)
- supported-operation routed accuracy 42.188%(37.349%–47.181%)
- near-domain unsupported-operation rejection 77.083%(70.642%–82.462%)
- ordinary out-of-domain rejection 100%(86.202%–100%)
- provider/planner error 0, invalid plan 0
- language-group accuracy: Korean 47% ~ Japanese 61%

최종 v10 error taxonomy는 missed route 199개, false route 44개, wrong-endpoint route 23개였습니다. missed route 중 162개는 operation-fit, 37개는 capability-fit에 귀속되었습니다. 이는 v10에 맞춰 retune할 이유가 아니라 limitation signal로 보존합니다. 추가 operation-fit optimization은 implementation 전에 새로운 untouched holdout을 예약해야 하며 v10은 이제 consumed regression evidence입니다.



### v11 pairwise operation-fit generalization

v10 이후 threshold/margin variant와 replacement bi-encoder를 v5 development/calibration만 사용해 평가했습니다. global margin, two-tier rescue, multilingual MPNet, multilingual E5 어느 것도 concise multilingual MiniLM bi-encoder보다 사전 등록된 robustness objective를 개선하지 못했습니다. pairwise reranking experiment가 v5 dev/calibration에서 해당 objective를 처음 넘어선 alternative scoring form이었습니다. sigmoid-normalized pair logit과 `min_score = 0.01`을 사용한 `BAAI/bge-reranker-v2-m3`는 71.354% robustness를 기록해 MiniLM bi-encoder의 69.792%를 넘어섰습니다.

pairwise result를 확인하기 전에 v11은 이미 supported operation 384개, near-domain unsupported operation 192개, ordinary out-of-domain request 24개로 구성된 새로운 600-case six-language test-only holdout으로 예약되어 있었습니다. 고정된 BGE candidate는 2026-09-26 source revision `57af2fd18d254fa1a9cd5855a158ae74b94adfc7`, corpus SHA-256 `efa8cd371bc7613895e44a915d78c77f5b88239c64a8de52d9c407839660d816`에서 한 번 평가했습니다. artifact `benchmark-operation-fit-v11-heldout-36239340782`의 SHA-256은 `f977511c7d65bc94e2dba9142b6cedf378ceaae1b8418c351e85b550f191dfd1`입니다.

최종 BGE stack 결과는 다음과 같습니다:

- overall accuracy 51.667%
- supported-operation routed accuracy 25.781%
- near-domain unsupported-operation rejection 97.396%
- ordinary out-of-domain rejection 100%
- balanced operation score 61.589%
- provider/planner error 0, invalid plan 0
- missed route 277개(이 중 operation-fit 귀속 251개)

BGE 결과는 더 강한 rejection을 얻는 대신 supported recall을 크게 희생했으므로, 이미 고정된 MiniLM 0.40 configuration을 **이미 소비된** v11 corpus에서 tuning이 아닌 paired diagnostic 목적으로 한 번 실행했습니다. 해당 baseline은 overall accuracy 54.833%, supported-operation routed accuracy 40.625%, near-domain rejection 77.604%, ordinary OOD rejection 100%, balanced operation score 59.115%를 기록했습니다. diagnostic artifact `benchmark-operation-fit-v11-baseline-diagnostic-36240431389`의 SHA-256은 `1048405ab34b41371004247e15934f5086a53977a14d4957bd14c6d69e194dee`입니다.

따라서 pairwise candidate는 **사전 등록된 balanced objective에서 +2.474 percentage-point 개선**을 generalize했지만 overall accuracy나 supported recall 개선은 아니었습니다.
따라서 SchemaRouter는 BGE를 library default로 선택하지 않고 pairwise scoring을 optional bounded backend로 제공합니다. v11은 이미 소비된 evidence이며 이후 hybrid rule, threshold, representation, model 선택에 사용해서는 안 됩니다.

### 변경 후 operation holdout (v7)

`benchmarks/decision-routing-v7-operation-post-change-holdout.json`은 bounded operation-fit embedding surface에서 tool-domain label을 제거한 뒤 예약한 600-case six-language test-only corpus입니다. supported operation 384개, near-domain unsupported operation 192개, ordinary out-of-domain request 24개를 포함하며 normalized query는 v2~v6와 겹치지 않도록 검증됩니다.

corpus는 label-cleaned operation-fit implementation을 측정하기 전에 추가되었습니다. operation-fit threshold 선택에 v7을 사용하지 않습니다. v5에서만 calibration하고 threshold를 고정한 뒤 post-change generalization claim을 위해 v7을 한 번 평가합니다. v6는 operation-fit input representation 변경 전에 이미 소비되었으므로 반복 v6 run은 regression evidence일 뿐입니다.


### 예약된 operation-alias holdout (v8)

`benchmarks/decision-routing-v8-operation-alias-holdout.json`은 trusted endpoint operation alias를 추가하기 전에 예약한 새로운 600-case six-language holdout입니다. supported-operation 384개, near-domain unsupported-operation 192개, ordinary out-of-domain 24개를 포함하며 normalized query는 v2~v7과 겹치지 않습니다.

v8은 alias implementation 전에 예약되었지만 초기 alias-aware calibration workflow의 per-threshold diagnostic step이 실수로 v8을 참조했습니다. 이 때문에 threshold sweep 전체에 v8이 노출되어 현재는 consumed diagnostic data로 취급하며 untouched generalization claim에 사용할 수 없습니다. workflow는 threshold 선택 중 이미 소비된 v7 diagnostic corpus를 사용하도록 수정되었습니다.


### Alias-aware threshold 선택 규칙

trusted `EndpointSpec.operation_aliases` 추가 후 operation-fit threshold 선택에는 v5와 이미 소비된 v7 diagnostic corpus만 사용합니다. 각 threshold에서 supported-operation accuracy와 near-domain unsupported-operation accuracy의 산술평균으로 corpus별 balanced operation score를 계산합니다. primary robustness score는 v5 calibration balanced score와 v7 diagnostic balanced score 중 더 낮은 값입니다.

이 robustness score를 최대화하는 threshold를 고정합니다. 첫 tie-breaker는 v5 development balanced accuracy이며 두 번째는 supported-request recall 보존을 위해 더 낮은 threshold를 선호합니다. consumed v8과 reserved v9는 threshold 선택이나 alias design에 참여할 수 없습니다. v5와 이미 소비된 v7 diagnostic에서 alias vocabulary와 threshold를 고정한 뒤 v9를 한 번 평가합니다.


### 예약된 alias-aware holdout (v9)

`benchmarks/decision-routing-v9-operation-alias-holdout.json`은 v8 workflow contamination을 발견한 뒤 alias-aware calibration result를 확인하기 전에 예약한 replacement untouched 600-case six-language holdout입니다. supported operation 384개, near-domain unsupported operation 192개, ordinary out-of-domain request 24개를 포함하며 normalized query는 v2~v8과 겹치지 않습니다.

v9는 GitHub Actions에서 manual-only이며 threshold gate가 적용됩니다. v5와 이미 소비된 v7 diagnostic corpus를 사용해 alias vocabulary와 operation-fit threshold를 고정하기 전에는 실행하지 않습니다.

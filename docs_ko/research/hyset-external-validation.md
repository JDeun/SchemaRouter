# HYSET 외부 검증 재학습 프로토콜

이 프로토콜은 HYSET 저자들이 논문 체크포인트를 공개하지 않기로 한 뒤 허용한 대체 비교 절차를 기록합니다. 이는 HYSET의 공개 논문 체크포인트나 논문 수치를 재현하는 절차가 아닙니다.

## 고정된 업스트림 입력

- HYSET 저장소: `stormwther18/HYSET`
- HYSET 커밋: `93808cb8d633b6b685f0f9353923b27c2ad7ad81`
- 쿼리 인코더: `reasonwang/ToolGen-Qwen2.5-1.5B-Tool-Retriever`
- 평가 ID: 고정된 HYSET 커밋의 `data/test_query_ids/*_test_query_ids.json` 6개 파일
- 원본 ToolBench instruction: 업스트림 ToolBench Data Release에서 확보하며 SchemaRouter에서 재배포하지 않습니다.

HYSET 저자들은 업스트림 issue #1에서 `best.pt`를 공개하지 않으며 공개 코드와 데이터로 새 체크포인트를 학습·평가하는 것을 명시적으로 허용했습니다. 따라서 결과 체크포인트는 반드시 **독립적으로 재학습한 HYSET(independently retrained HYSET)** 으로 표기하며, 공개된 논문 체크포인트라고 표현하지 않습니다.

## 학습 경계

고정된 커밋의 HYSET 공개 `train_hyset.sh`를 사용합니다. held-out test ID 제외 규칙을 유지합니다. 문서화된 seed 42 설정에서 시작하며 6개 held-out test split을 대상으로 튜닝하지 않습니다.

공개 README에는 다음 두 가지 논문 정렬 설정이 기록되어 있습니다.

- BERT: `--encoder_type bert --d_z 768 --seed 42`
- Qwen: `--encoder_type qwen --d_z 1536 --seed 42`

공개 기본값에는 `M=5`, `K_neg=64`, `K1=15`, `K_pool=20`, `eta=0.3`, `lambda_interaction=0.01`이 포함됩니다. `eta=0.3` 설정에 필요한 execution-reward cache를 새로운 judge/model 선택 없이 공개 artifact만으로 재현할 수 없다면 annotation-only ablation(`--eta 0`, reward cache 없음)을 실행하고 이를 명시적으로 표시합니다. 새로 선택한 judge를 조용히 대체해서는 안 됩니다.

정확한 encoder revision, ToolBench data digest, 명령줄, 하드웨어, CUDA/PyTorch 버전, wall time, 생성된 checkpoint SHA-256을 기록합니다.

## 평가

HYSET의 공개 `src/evaluate_hyset.py`를 수정하지 않고 공개된 6개 split ID 파일 모두에서 실행합니다. 다음 native metric을 유지합니다.

- Recall@3 / Recall@5
- NDCG@3 / NDCG@5
- COMP@3 / COMP@5
- PredictedSetExactMatch
- MeanPredictedCardinality

SchemaRouter 측에서는 표현 가능한 범위에서 동일한 query ID와 ground-truth tool identity surface를 평가합니다. SchemaRouter 고유의 selected-set size와 latency는 HYSET의 native set prediction과 분리합니다. ToolBench에서 output-field label을 추론하지 않습니다.

## 보고 규칙

1. 독립적으로 재학습한 체크포인트를 저자들이 공개한 `best.pt`인 것처럼 논문 표와 비교하지 않습니다.
2. 학습 실패, OOM, 공개 데이터 부재, 음성 결과도 보고합니다.
3. held-out test metric을 사용해 parameter를 선택하지 않습니다.
4. HYSET-native와 SchemaRouter-native metric의 이름을 분리하며, 직접 비교 가능한 tool-retrieval metric만 같은 표에 둘 수 있습니다.
5. 최초 scored run 전에 새로 다운로드한 모든 model/data revision을 고정합니다.

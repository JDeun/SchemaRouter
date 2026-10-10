# Laya

SchemaRouter는 [Laya](https://github.com/NandhaKishorM/laya)를 optional local `DecisionBackend`로 사용할 수 있습니다.

Laya는 general text-generation model이 아니라 non-autoregressive decision model입니다. SchemaRouter 내부의 agent runtime이 아니며 adapter는 finite `choice` primitive만 사용합니다. Backend는 SchemaRouter가 이미 authorize한 opaque option ID 중 하나를 선택할 수 있지만 tool, endpoint, field, parameter, credential, execution permission, multi-step tool loop를 만들 수 없습니다.

## 설치

Current distribution에서는 optional `laya` extra로 제공합니다.

```bash
pip install -e ".[laya]"
```

해당 integration이 포함된 release의 packaged form:

```bash
pip install "schemarouter[laya]"
```

Extra는 Laya runtime/local model dependency를 설치합니다. Model weight는 cache에 없을 때 checkpoint 최초 load 시 Laya/Hugging Face가 download합니다.

## Automatic local routing

기본적으로 request state에서 English/multilingual checkpoint를 Laya가 선택합니다.

```python
from schemarouter.integrations import LayaDecisionBackend
backend = LayaDecisionBackend(min_confidence=0.65)
```

Adapter는 user query, optional bounded decision context, finite option ID, option label/description을 전달하며 `DecisionOption.metadata`는 전달하지 않습니다. Selected checkpoint/routing reason 같은 Laya metadata는 non-authoritative `DecisionResult.metadata`로만 반환합니다.

## Checkpoint 고정

```python
backend = LayaDecisionBackend(
    model="multilingual",
    device="mps",
    min_confidence=0.65,
)
```

Common checkpoint는 `english`, `multilingual`, `typed-decisions`이며 SchemaRouter는 benchmark-specific `typed-decisions`를 자동 선택하지 않습니다.

`device`는 explicit performance control입니다. `cpu`, `cuda`, `mps`를 사용할 수 있습니다. Apple Silicon의 `mps`는 PyTorch Metal Performance Shaders backend이며 MLX-native path가 아닙니다. 현재 Laya runtime은 MPS에서 float32를 사용하므로 memory/latency가 CUDA와 크게 다를 수 있습니다.

Laya가 다른 device로 fallback하면 SchemaRouter는 `requested_device`와 가능한 경우 `actual_device`를 non-authoritative decision metadata에 기록합니다. 실제 CPU 실행을 GPU benchmark로 잘못 보고하는 것을 방지합니다.

## Long-running process에서 preload

```python
backend = LayaDecisionBackend(preload=True, max_loaded=2)
```

`model=` 고정 시 해당 checkpoint를 preload합니다. Automatic language routing에서는 `english`와 `multilingual`만 preload하며 `typed-decisions`는 implicit download하지 않습니다. Preload는 per-case benchmark timing 전 backend construction에서 일어납니다. Resident checkpoint는 사용 가능한 CPU/GPU/MPS memory에 맞게 선택합니다. Preload는 trusted local configuration이며 model/request가 제어하지 않습니다.

## Async planning

Laya inference는 synchronous입니다. `async_mode=True`이면 local inference를 worker thread로 옮겨 async planner event loop에서 blocking call을 직접 실행하지 않습니다.

```python
backend = LayaDecisionBackend(async_mode=True)
```

Single forward pass 자체를 asynchronous하게 만드는 것은 아니며 async SchemaRouter contract만 보존합니다.

## Confidence와 abstention

```python
backend = LayaDecisionBackend(min_confidence=0.70)
```

SchemaRouter는 confidence-based abstention 전에 returned option ID를 검사하므로 unknown option은 low confidence여도 fail-closed합니다. Confidence는 execution authority가 아니라 provider/model evidence이며 operational threshold로 사용하기 전에 실제 workload에서 calibration해야 합니다.

## Trust boundary

- locally authorized finite option ID만 노출
- unknown ID fail-closed
- `DecisionOption.metadata` 미전달
- Hugging Face token은 trusted local router configuration에 유지
- provider metadata는 execution authority를 부여할 수 없음
- SchemaRouter가 final decision을 local에서 재검증
- deterministic fallback policy는 SchemaRouter 소유

## 현재 범위와 제한

Adapter는 Laya single-select `choice`만 generic `DecisionBackend`에 mapping합니다. `max_selections > 1` request는 fail-closed하여 planner가 configured deterministic/error fallback을 적용하게 합니다. Laya의 score/probability primitive를 추가하려면 finite selection semantics에 억지로 넣지 말고 별도 typed contract가 필요합니다.

Laya quality는 checkpoint/language/option count/domain에 의존합니다. High-cardinality choice set은 더 큰 option/head budget 또는 shortlist strategy가 필요할 수 있습니다. Third-party/upstream benchmark 수치를 SchemaRouter workload 보장으로 취급하지 마십시오.

Default backend/confidence threshold를 정하기 전에 shared SchemaRouter corpus에서 정확한 checkpoint/hardware를 측정하십시오.

## Benchmark

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya
```

Checkpoint/device 고정:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya \
  --laya-model multilingual \
  --laya-device mps \
  --laya-min-confidence 0.65 \
  --hardware-label "Apple M4 16GB"
```

Mixed-language 장시간 benchmark에서는 `--laya-preload`로 repeated cold checkpoint load를 피할 수 있습니다. JSON/CSV row는 selected checkpoint와 가능한 경우 requested/actual device를 기록하며 report는 platform metadata와 optional `--hardware-label`도 기록합니다. 결과 공개 시 exact Laya version, checkpoint, hardware/device, preload policy, confidence threshold를 기록해야 합니다.

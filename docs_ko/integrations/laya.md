# Laya

SchemaRouter는 [Laya](https://github.com/NandhaKishorM/laya)를 optional local `DecisionBackend`로 사용할 수 있습니다.

Laya는 범용 text-generation model이 아니라 non-autoregressive decision model입니다. SchemaRouter 내부의 agent runtime이 아닙니다. Adapter는 Laya의 유한한 `choice` primitive만 사용합니다. Backend는 SchemaRouter가 이미 승인한 opaque option ID 중 하나를 선택할 수 있지만 tool, endpoint, field, parameter, credential, execution permission 또는 multi-step tool loop를 만들어낼 수 없습니다.

## 설치

Laya support는 현재 SchemaRouter distribution에 optional `laya` extra로 포함됩니다.

개발 checkout:

```bash
pip install -e ".[laya]"
```

이 integration이 포함된 다음 release부터 packaged 설치 형식은 다음과 같습니다:

```bash
pip install "schemarouter[laya]"
```

The extra installs the Laya runtime and its local model dependencies. Model weights are downloaded
by Laya/Hugging Face only when a checkpoint is first loaded unless they are already cached.

## 자동 local routing

기본적으로 SchemaRouter는 request state를 바탕으로 Laya가 English 또는 multilingual checkpoint를 선택하도록 합니다:

```python
from schemarouter.integrations import LayaDecisionBackend

backend = LayaDecisionBackend(
    min_confidence=0.65,
)
```

Adapter는 다음 항목을 전달합니다:

- the user query;
- optional bounded decision context;
- finite option IDs;
- option labels and descriptions.

`DecisionOption.metadata`는 전달하지 않습니다.

Laya routing metadata such as the selected checkpoint and routing reason is returned only as
non-authoritative `DecisionResult.metadata`.

## Checkpoint 고정

Use `model=` when the application has already chosen the checkpoint:

```python
backend = LayaDecisionBackend(
    model="multilingual",
    device="mps",
    min_confidence=0.65,
)
```

Common Laya checkpoint names include `english`, `multilingual`, and
`typed-decisions`. SchemaRouter does not select the benchmark-specific
`typed-decisions` checkpoint automatically.

`device` is an explicit performance control. Use `cpu`, `cuda`, or `mps` when the runtime
should request a specific device. On Apple Silicon, `mps` uses PyTorch's Metal Performance
Shaders backend, executing through Apple's Metal stack. It is not an MLX-native path;
the current Laya runtime uses float32 on MPS, so memory use and latency can differ materially from
CUDA. If Laya falls back to another device, SchemaRouter records both
`requested_device` and, when the loaded agent exposes it, `actual_device` in non-authoritative
decision metadata. This prevents a GPU-requested run that actually executed on CPU from being
misreported as a GPU benchmark.

## 장기 실행 process용 preload

Laya can lazily load checkpoints, but switching between uncached checkpoints can dominate latency.
A server that has enough memory can preload checkpoints before the first decision:

```python
backend = LayaDecisionBackend(
    preload=True,
    max_loaded=2,
)
```

When `model=` is pinned, SchemaRouter preloads that checkpoint. In automatic language-routing
mode, it preloads only `english` and `multilingual`; the benchmark-specific
`typed-decisions` checkpoint is not downloaded implicitly. Preloading happens during backend
construction, before per-case benchmark timing starts. Choose resident checkpoints according to
available CPU/GPU/MPS memory. Preloading is trusted local configuration and is never controlled by
the model or request.

## Async planning

Laya inference is synchronous. With `async_mode=True`, SchemaRouter moves the local inference call
to a worker thread so an async planner does not execute the blocking call directly on the event
loop:

```python
backend = LayaDecisionBackend(
    async_mode=True,
)
```

This does not make a single model forward pass intrinsically asynchronous; it only preserves the
async SchemaRouter contract.

## Confidence와 abstention

Set `min_confidence` to make a valid low-confidence Laya choice abstain:

```python
backend = LayaDecisionBackend(
    min_confidence=0.70,
)
```

SchemaRouter checks the returned option ID **before** confidence-based abstention. An unknown option
therefore fails closed even when Laya reports low confidence.

Confidence is provider/model evidence, not execution authority. It should be calibrated on the
actual workload before it is used as an operational threshold.

## Trust boundary

The adapter preserves the same bounded-decision invariants as the Jev and Ollama integrations:

- only locally authorized finite option IDs are exposed;
- unknown IDs fail closed;
- `DecisionOption.metadata` is not forwarded;
- Hugging Face tokens stay in trusted local router configuration;
- provider metadata cannot grant execution authority;
- SchemaRouter revalidates the final decision locally;
- deterministic fallback policy is owned by SchemaRouter.

## 현재 범위와 제한

The SchemaRouter adapter maps only Laya's single-select `choice` primitive to the
generic `DecisionBackend` contract. A request with `max_selections > 1` fails closed so the
planner can apply its configured deterministic/error fallback rather than silently treating a
multi-select surface as single-select. Laya also exposes score/probability-oriented primitives, but
adding those to SchemaRouter would require a separate typed contract rather than overloading finite
selection semantics.

Laya quality is checkpoint-, language-, option-count-, and domain-dependent. In particular,
high-cardinality choice sets can require a larger option/head budget or a shortlist strategy.
Do not treat published third-party or upstream benchmark numbers as a guarantee for a SchemaRouter
workload.

Use the shared SchemaRouter corpus to measure the exact checkpoint and hardware before choosing a
default backend or confidence threshold.

## Benchmark

Run Laya on the same corpus used by deterministic, embedding, Jev, and Ollama paths:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya
```

Pin a checkpoint or device when needed:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya \
  --laya-model multilingual \
  --laya-device mps \
  --laya-min-confidence 0.65 \
  --hardware-label "Apple M4 16GB"
```

For a long-running benchmark on mixed languages, `--laya-preload` avoids repeated cold checkpoint
loads. JSON/CSV rows record the selected checkpoint plus requested/actual device when available.
The report also records platform metadata and the optional `--hardware-label`. Record the exact
Laya version, checkpoint, hardware/device, preload policy, and confidence threshold when publishing
results.

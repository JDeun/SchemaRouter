# Laya

SchemaRouter는 Laya를 optional local `DecisionBackend`로 사용할 수 있습니다. Laya는 일반 text-generation agent가 아니라 non-autoregressive decision model이며 finite `choice` primitive만 사용합니다.

## 설치와 local routing

```bash
pip install "schemarouter[laya]"
```

`LayaDecisionBackend(min_confidence=0.65)`는 기본적으로 request state에 따라 English/multilingual checkpoint를 선택할 수 있습니다. user query, optional bounded context, finite option ID/label/description만 전달하며 `DecisionOption.metadata`는 전달하지 않습니다.

## Checkpoint/device 고정

`model="multilingual"`, `device="mps"`처럼 명시할 수 있습니다. 일반 checkpoint 이름은 `english`, `multilingual`, `typed-decisions`이며 benchmark 전용 `typed-decisions`는 자동 선택하지 않습니다.

device는 `cpu`, `cuda`, `mps`를 지원합니다. Apple Silicon의 `mps`는 PyTorch Metal Performance Shaders 경로이며 MLX-native가 아닙니다. 실제 device가 fallback되면 requested/actual device를 non-authoritative metadata에 기록합니다.

## Preload와 async

장기 process는 `preload=True, max_loaded=2`로 checkpoint를 미리 올릴 수 있습니다. automatic mode에서는 english/multilingual만 preload합니다. `async_mode=True`는 blocking local inference를 worker thread로 옮겨 event loop를 막지 않게 할 뿐 forward pass 자체를 async로 만들지는 않습니다.

## Confidence와 신뢰 경계

unknown option ID는 confidence abstention보다 먼저 fail-closed됩니다. confidence는 execution authority가 아니라 model evidence이며 실제 workload에서 calibration해야 합니다. credential/provider metadata도 authority를 부여하지 않습니다.

현재 generic contract에는 single-select `choice`만 매핑하며 `max_selections > 1`은 fail-closed됩니다. 품질은 checkpoint/language/option count/domain에 따라 달라지므로 실제 corpus와 hardware에서 측정해야 합니다.

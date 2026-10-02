# System One 호환 decision provider

SchemaRouter는 typed System One decision contract와 호환되는 provider를 하나의 bounded backend로 사용할 수 있습니다. hosted Jev, self-hosted decision model, 향후 compatible runtime이 같은 client contract를 제공하면 동일 adapter를 공유할 수 있습니다.

## 설치

```bash
pip install "schemarouter[systemone]"
```

기존 `schemarouter[jev]` extra도 계속 지원합니다.

## Provider 연결

```python
from schemarouter.integrations import SystemOneDecisionBackend

backend = SystemOneDecisionBackend(
    base_url="http://127.0.0.1:8000/v1",
    model="kev-4b",
    provider_name="kev-local",
    min_confidence=0.70,
)
```

model은 SchemaRouter가 제공한 finite option ID 중에서만 선택할 수 있습니다. server/model이 바뀌었다는 이유만으로 model-specific SchemaRouter class가 필요하지 않습니다.

## 로컬에 남는 권한

provider는 decision signal이지 execution authority가 아닙니다. SchemaRouter가 finite candidate set 생성, provider-visible metadata 제한, option ID/confidence 검증, abstention rule, execution plan 생성/검증, policy/schema/fingerprint/execution authority를 계속 소유합니다.

direct Laya Python runtime에는 `LayaDecisionBackend`, compatible HTTP endpoint 뒤의 Laya/Kev/System One model에는 `SystemOneDecisionBackend`가 적합합니다. `JevDecisionBackend`도 backward compatible하게 유지됩니다.

## 새 모델 평가

wire compatibility가 quality equivalence를 뜻하지 않습니다. production model 교체 전 같은 frozen workload에서 exact-route accuracy, unsupported/OOD rejection, false-route rate, calibration/abstention, language/route별 동작, p50/p95 latency/residency, provider/runtime error, authority violation을 측정해야 합니다.

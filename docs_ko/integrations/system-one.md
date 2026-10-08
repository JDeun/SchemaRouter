# System One 호환 decision provider

SchemaRouter는 typed System One decision contract와 호환되는 모든 provider를 하나의 bounded backend를 통해 사용할 수 있습니다.

이 integration은 model-neutral합니다. Hosted Jev, self-hosted decision model, 향후 호환 runtime은 compatible System One client contract를 제공한다면 동일한 SchemaRouter adapter를 공유할 수 있습니다.

## 설치

```bash
pip install "schemarouter[systemone]"
```

기존 Jev 전용 extra도 계속 지원합니다.

```bash
pip install "schemarouter[jev]"
```

## 호환 provider 연결

```python
from schemarouter.integrations import SystemOneDecisionBackend

backend = SystemOneDecisionBackend(
    base_url="http://127.0.0.1:8000/v1",
    model="kev-4b",
    provider_name="kev-local",
    min_confidence=0.70,
)
```

Backend를 일반 SchemaRouter decision surface에 전달합니다. Model은 SchemaRouter가 제공한 유한한 option ID 중에서만 선택할 수 있습니다.

Model 변경은 일반적으로 configuration 변경만 필요합니다.

```python
backend = SystemOneDecisionBackend(
    base_url=SYSTEM_ONE_BASE_URL,
    model=SYSTEM_ONE_MODEL,
    provider_name=SYSTEM_ONE_PROVIDER,
)
```

Server가 바뀐다는 이유만으로 model별 SchemaRouter class가 필요하지 않습니다.

## 로컬에 남는 것

호환 provider는 decision signal이지 execution authority가 아닙니다.

SchemaRouter는 계속 다음을 담당합니다.

- 등록된 schema에서 유한한 candidate set 구성
- provider-visible question에서 `DecisionOption.metadata` 제외
- 반환된 option ID를 local candidate set과 대조해 검증
- malformed, non-finite 또는 범위를 벗어난 confidence value 거부
- 설정된 confidence abstention rule 적용
- execution plan을 로컬에서 구성하고 검증
- policy, schema, fingerprint, execution authority 유지

Provider는 tool, endpoint, field, argument 또는 permission을 새로 만들 수 없습니다.

## Direct Laya와 System One wire compatibility

`LayaDecisionBackend`는 공식 Python Laya package를 직접 실행할 때 유용하며 local checkpoint routing과 CPU/CUDA/MPS control도 포함합니다.

Laya-compatible, Kev-compatible 또는 다른 System One model이 호환 endpoint 뒤에서 서비스되는 경우에는 `SystemOneDecisionBackend`를 사용합니다. 이렇게 하면 deployment/runtime 선택을 SchemaRouter planning semantics 밖에 둘 수 있습니다.

## Jev compatibility

`JevDecisionBackend`는 계속 사용할 수 있고 backward compatible합니다. 현재는 동일한 generic provider contract의 TypeSafe Jev specialization이므로 기존 application은 migration할 필요가 없습니다.

## 새로운 model 평가

Wire compatibility가 quality equivalence를 의미하지는 **않습니다**. Production decision model을 교체하기 전 동일한 frozen workload에서 후보를 평가하고 다음을 기록합니다.

- exact-route accuracy
- unsupported 및 out-of-domain rejection
- false-route rate
- calibration/abstention behavior
- 언어별·route별 동작
- p50/p95 latency와 model residency
- provider/runtime error
- authority violation

SchemaRouter research harness도 이 원칙을 따릅니다. Infrastructure compatibility는 재사용할 수 있지만 model promotion에는 독립적인 evidence가 필요합니다.

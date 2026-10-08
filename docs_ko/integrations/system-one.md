# System One 호환 의사결정 공급자

SchemaRouter는 타입이 지정된 System One 의사결정 계약과 호환되는 모든 공급자를 **하나의 제한된 범위의 백엔드**로 사용할 수 있습니다.

이 통합은 모델 중립적입니다. 호스팅 Jev, 자체 호스팅 의사결정 모델, 향후의 호환 런타임이 동일한 System One 클라이언트 계약을 제공한다면 SchemaRouter 어댑터를 공유할 수 있습니다.

## 설치

```bash
pip install "schemarouter[systemone]"
```

기존 Jev 전용 extra도 계속 지원합니다.

```bash
pip install "schemarouter[jev]"
```

## 호환 공급자 연결

```python
from schemarouter.integrations import SystemOneDecisionBackend

backend = SystemOneDecisionBackend(
    base_url="http://127.0.0.1:8000/v1",
    model="kev-4b",
    provider_name="kev-local",
    min_confidence=0.70,
)
```

백엔드를 일반적인 SchemaRouter 의사결정 인터페이스에 전달하십시오. 모델은 SchemaRouter가 제공한 **유한한 후보 옵션 ID**에서만 선택할 수 있습니다.

모델 변경에는 일반적으로 구성만 수정하면 됩니다.

```python
backend = SystemOneDecisionBackend(
    base_url=SYSTEM_ONE_BASE_URL,
    model=SYSTEM_ONE_MODEL,
    provider_name=SYSTEM_ONE_PROVIDER,
)
```

서버가 변경됐다는 이유만으로 모델별 SchemaRouter 클래스를 새로 만들 필요는 없습니다.

## 로컬에 유지되는 권한

호환 공급자가 제공하는 것은 의사결정 신호이지 실행 권한이 아닙니다.

SchemaRouter는 계속 다음 작업을 책임집니다.

- 등록된 스키마로 유한한 후보 집합을 구성합니다.
- 공급자가 볼 수 있는 질문에서 `DecisionOption.metadata`를 제외합니다.
- 반환된 옵션 ID가 로컬 후보 집합에 속하는지 검증합니다.
- 형식이 잘못됐거나 유한하지 않거나 범위를 벗어난 confidence 값을 거부합니다.
- 설정된 confidence에 따른 abstention(선택 보류) 규칙을 적용합니다.
- 실행 계획을 로컬에서 작성하고 검증합니다.
- 정책, 스키마, 지문, 실행 권한을 로컬에서 유지합니다.

공급자는 도구, 엔드포인트, 필드, 인자 또는 권한을 새로 만들어 낼 수 없습니다.

## 직접 실행하는 Laya와 System One 전송 호환성

공식 Python Laya 패키지를 직접 사용하는 경우에는 `LayaDecisionBackend`가 유용합니다. 로컬 체크포인트 기반 라우팅과 CPU/CUDA/MPS 설정도 포함됩니다.

Laya 호환 모델, Kev 호환 모델 또는 기타 System One 모델을 호환 엔드포인트 뒤에서 서비스한다면 `SystemOneDecisionBackend`를 사용하십시오. 이렇게 하면 배포·런타임 선택을 SchemaRouter의 계획 의미론과 분리할 수 있습니다.

## Jev 호환성

`JevDecisionBackend`는 계속 제공되며 하위 호환성을 유지합니다. 이제 동일한 범용 공급자 계약을 사용하는 TypeSafe Jev 특화 구현이므로 기존 애플리케이션을 마이그레이션할 필요가 없습니다.

## 새 모델 평가

전송 프로토콜이 호환된다고 해서 **품질이 동등한 것은 아닙니다.** 운영 중인 의사결정 모델을 교체하기 전에 동일하게 동결된 워크로드에서 후보를 평가하고 다음 정보를 기록해야 합니다.

- 정확한 라우트 선택 정확도(exact-route accuracy)
- 지원하지 않는 요청과 분포 밖 요청(OOD)의 거부 성능
- 잘못된 라우트 선택 비율(false-route rate)
- confidence 보정과 선택 보류 동작(calibration/abstention)
- 언어별 및 라우트별 성능
- p50/p95 지연 시간과 모델 메모리 상주 상태
- 공급자·런타임 오류
- 실행 권한 위반

SchemaRouter의 연구 하네스도 이 원칙을 따릅니다. 인프라 호환성은 재사용할 수 있지만, 모델의 운영 승격에는 독립적인 성능 근거가 필요합니다.

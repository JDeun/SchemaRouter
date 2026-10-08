# 호스트가 적용하는 기능 운영 제약

호스트는 동등한 기능에 선택적인 운영 메타데이터를 부여하고 SchemaRouter에 정책 결정 권한을 이전하지 않은 채 필수 제약을 적용할 수 있습니다.

```python
from schemarouter import CapabilityOperationalMetadata, HostCapabilityConstraints, evaluate_operational_constraints

result = evaluate_operational_constraints(
    CapabilityOperationalMetadata(locality="local", estimated_latency_ms=25),
    HostCapabilityConstraints(allowed_localities={"local"}, max_latency_ms=100),
)
```

필수 제약은 지연 시간, 비용, 로컬·원격 실행 여부, 데이터 보관 지역, 개인정보 등급, 네트워크 사용 여부를 다룹니다. 필수 제약이 선언되어 있으나 평가에 필요한 메타데이터를 알 수 없다면 `metadata_unknown`으로 **안전하게 거부**합니다.

선호 조건(soft preference)은 적격하지 않은 후보를 적격하게 바꾸지 않습니다. 모든 필수 제약을 통과한 후보에 대해서만 결정론적 선호 점수를 계산합니다. 선호 조건만을 위한 메타데이터가 누락된 경우에는 해당 선호 정보를 자연스럽게 무시합니다.

이 API는 권한을 추론하거나 실시간 가격을 조회하거나 예산을 배정하거나 기능을 실행하지 않습니다. 제약을 정의하고 정책 권한을 유지하는 주체는 호스트입니다.

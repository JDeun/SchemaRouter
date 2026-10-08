# 호스트 주도의 기능 계약 협상

호스트가 명시적인 출력 계약을 제출하면 SchemaRouter는 등록된 기능 계약과의 호환성을 결정론적으로 평가할 수 있습니다. 결과에서는 정확히 일치하는 후보, 호환 가능한 후보, 변환 가능한 후보, 비호환 후보, 판단 불가 후보, 정책으로 거부된 후보, 현재 사용할 수 없는 후보를 구분합니다.

```python
from schemarouter import CapabilityNegotiationRequest, negotiate_capabilities

result = negotiate_capabilities(
    CapabilityNegotiationRequest(required_outputs=required_fields),
    capabilities,
    authorized_capability_ids=host_allow_set,
    unavailable_capability_ids=unavailable,
    context=compatibility_context,
)
```

권한 범위는 항상 교집합이며 **절대로 확대하지 않습니다**. 호스트가 빈 허용 집합을 제공하면 결과도 실질적으로 빈 집합입니다. 사용할 수 없는 후보와 계약이 일치하지 않는 후보는 구분합니다. 단위 변환은 호환성 컨텍스트에 명시적으로 선언된 경우에만 변환 가능하다고 보고하며 SchemaRouter가 직접 변환하지는 않습니다.

협상은 계약 조회 기능이지 계획 수립이나 실행이 아닙니다. 기존의 상태 비저장 쿼리 기반 라우팅도 독립적으로 계속 지원합니다.

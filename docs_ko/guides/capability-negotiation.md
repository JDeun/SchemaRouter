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

최상위 JSON 타입이 같다는 사실만으로 제약이 있는 필드 계약의 호환성을 입증할 수는 없습니다. 요구 스키마에 `enum`, 숫자 범위, `items`, 객체 속성 등의 제약이 있으면 제공 스키마에도 같은 제약이 유지되어야 합니다. 서로 다른 제약은 호환성을 입증하지 못했으므로 `unknown`으로 반환하며, 더 엄격한 제약도 별도 증명이 없으면 동일하게 처리합니다. 설명용 메타데이터는 이 비교에 영향을 주지 않으며, 정수 출력은 여전히 숫자 요구를 충족할 수 있습니다. 이 보수적인 선언 비교는 실행 시 실제 값 검증을 대체하지 않습니다.

협상은 계약 조회 기능이지 계획 수립이나 실행이 아닙니다. 기존의 상태 비저장 쿼리 기반 라우팅도 독립적으로 계속 지원합니다.

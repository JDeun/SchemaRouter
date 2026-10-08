# 기능 적격성에 관한 설명

SchemaRouter는 호스트에 이미 노출된 기능이 왜 실행 후보로 적격하거나 제외되었는지 구조화된 설명을 반환할 수 있습니다. 사유에는 안정적인 코드가 사용되고 하위 사유를 포함할 수 있으므로 어댑터와 관측 시스템은 자유 형식의 문장을 파싱하지 않고도 사유 트리를 표시할 수 있습니다.

```python
from schemarouter import CapabilityEligibilityReason, explain_capability_eligibility

explanation = explain_capability_eligibility(
    "materials.summary",
    visible=True,
    reasons=[CapabilityEligibilityReason(code="method_unhealthy")],
)
```

지원하는 사유 유형에는 상태, 의미·타입·단위 호환성, 건강 상태, 계약 변경, 정책, 개인정보 보호, 실행 위치, 비용, 알 수 없거나 지원되지 않는 조건이 포함됩니다.

## 비공개 정보 보호 경계

이 API를 호출하는 호스트는 해당 기능이 **이미 노출된 기능인지** 명시해야 합니다. `visible=False`이면 전달한 사유와 무관하게 `None`을 반환합니다. 따라서 설명 인터페이스를 통해 비공개 기능의 존재 여부나 해당 기능을 숨긴 권한 규칙을 알아낼 수 없습니다. 설명은 라우팅 적격성만 나타내며 기능 실행 권한을 부여하거나 실제 실행하지 않습니다.

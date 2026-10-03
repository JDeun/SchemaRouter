# Capability eligibility 설명

SchemaRouter는 host에 이미 보이는 capability가 왜 eligible 또는 excluded 상태인지 구조화된 설명으로 반환할 수 있습니다. Reason은 안정적인 code를 사용하며 child reason을 가질 수 있어 adapter와 observability 계층이 free text를 파싱하지 않고 tree를 표시할 수 있습니다.

```python
from schemarouter import CapabilityEligibilityReason, explain_capability_eligibility

explanation = explain_capability_eligibility(
    "materials.summary",
    visible=True,
    reasons=[CapabilityEligibilityReason(code="method_unhealthy")],
)
```

Reason class는 state, semantic/type/unit compatibility, health, drift, policy, privacy, locality, cost, unknown/unsupported 조건을 포함합니다.

## Non-disclosure 경계

API는 capability가 host에 이미 visible한지 명시하도록 요구합니다. `visible=False`이면 전달된 reason과 무관하게 `None`을 반환합니다. 따라서 explanation surface를 통해 숨겨진 capability의 존재나 어떤 authorization rule이 이를 숨겼는지 추론할 수 없습니다. 설명은 routing eligibility만 기술하며 authorization을 부여하거나 capability를 실행하지 않습니다.

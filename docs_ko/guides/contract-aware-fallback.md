# Contract-aware fallback eligibility

Fallback eligibility는 host authorization, method health, capability-contract validation, contract drift, typed state eligibility, retrieval membership을 함께 평가할 수 있습니다.

```python
from schemarouter import evaluate_fallback_eligibility

result = evaluate_fallback_eligibility(
    authorized=True,
    healthy=True,
    contract_validation=validation,
)
```

따라서 transport가 정상이어도 선언된 contract가 missing, incompatible, unverifiable 또는 drifted이면 제외할 수 있습니다. `eligible_fallback_ids()`는 이미 평가된 candidate를 host가 제공한 순서대로 필터링할 뿐 실행하지 않습니다.

Contract/state metadata를 제공하지 않으면 기존 authorization + health 동작을 유지합니다. Host denial은 항상 우선하며 fallback이 권한을 확대할 수 없습니다. SchemaRouter는 eligibility/candidate 정보만 반환하고 실행, conversion, retry, response handling은 host가 담당합니다.

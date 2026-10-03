# Host-driven capability contract negotiation

Host는 명시적인 output contract를 제출하고 선언된 capability contract에 대한 결정적 compatibility 결과를 받을 수 있습니다. Negotiation은 exact, compatible, convertible, incompatible, unknown, policy-denied, unavailable candidate를 구분합니다.

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

Authorization은 항상 교집합이며 확장되지 않습니다. 빈 host allow-set은 그대로 실질적인 빈 집합이며 unavailable candidate는 contract mismatch와 구분됩니다. Unit conversion은 compatibility context에 명시적으로 선언된 경우에만 보고하며 SchemaRouter가 conversion을 실행하지 않습니다.

Negotiation은 contract query이며 planning이나 execution이 아닙니다. 기존 stateless query-based routing은 독립적으로 계속 지원됩니다.

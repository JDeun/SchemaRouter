# Host operational capability constraint

Host는 동등한 capability에 선택적 operational metadata를 부여하고 SchemaRouter에 policy 권한을 넘기지 않은 채 hard constraint를 적용할 수 있습니다.

```python
from schemarouter import CapabilityOperationalMetadata, HostCapabilityConstraints, evaluate_operational_constraints

result = evaluate_operational_constraints(
    CapabilityOperationalMetadata(locality="local", estimated_latency_ms=25),
    HostCapabilityConstraints(allowed_localities={"local"}, max_latency_ms=100),
)
```

Hard constraint는 latency, cost, local/remote execution, residency region, privacy class, network 사용을 다룹니다. Hard constraint가 선언되었는데 필요한 metadata가 없으면 `metadata_unknown`으로 fail closed합니다. Soft preference는 ineligible candidate를 eligible로 바꾸지 않으며, 모든 hard constraint를 통과한 candidate에 대해서만 결정적 preference score를 만듭니다. Soft preference에만 필요한 metadata가 없으면 제외하지 않습니다.

이 API는 permission을 추론하거나 dynamic price를 조회하거나 budget을 자동 할당하거나 capability를 실행하지 않습니다. Constraint 정의와 policy 권한은 host에 남습니다.

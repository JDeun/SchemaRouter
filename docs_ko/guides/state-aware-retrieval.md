# 상태 인식 capability retrieval

외부 런타임은 SchemaRouter에 워크플로 또는 실행 권한을 넘기지 않고도 명시적인 typed execution state를 기준으로 일반 capability retrieval 결과를 필터링할 수 있습니다.

기존 `retrieve(request, *, k=5)` facade는 stateless 계약과 하위 호환성을 그대로 유지합니다. 호스트 상태를 eligibility 판단에 반영해야 할 때는 명시적인 state-aware API를 사용합니다.

```python
from schemarouter import CapabilityFieldContract, TypedExecutionState

eligible = router.retrieve_state_aware(
    "material 조회를 계속해",
    execution_state=TypedExecutionState(...),
    state_requirements={
        "materials.summary": [
            CapabilityFieldContract(
                semantic_id="resource.material_id",
                json_schema={"type": "string"},
            )
        ]
    },
)
```

비동기 API는 `await router.aretrieve_state_aware(...)` 입니다. 호스트가 이미 `CapabilityRetrieval` 객체를 가지고 있다면 하위 수준의 `filter_retrieval_by_state(...)` 도 사용할 수 있습니다.

`state_requirements` 와 `state_preconditions` 는 호스트가 명시적으로 제공하는 계약 메타데이터입니다. SchemaRouter는 route 이름, parameter 이름, 설명, 이전 rank 위치 또는 숨겨진 미래 route에서 workflow precondition을 추론하지 않습니다.

선언된 requirement에 필요한 typed state가 없거나 호환되지 않으면 해당 후보는 fail-closed로 제외됩니다. 반대로 state requirement가 선언되지 않은 route는 기존 stateless 동작을 유지합니다. 따라서 기존 `router.retrieve(query, k=...)` 및 `router.aretrieve(...)` 호출은 원래의 `CapabilityRetrieval` 계약과 시그니처를 그대로 유지합니다.

이 API는 capability 정보만 반환합니다. 워크플로 선택, capability 실행, transaction commit/rollback, 호스트 상태 변경, retry scheduling, compensation 실행 또는 authorization 확대를 수행하지 않습니다. 정책, availability, 실행, retry, compensation 권한은 계속 호스트 런타임에 있습니다.

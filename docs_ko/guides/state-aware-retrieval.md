# 상태 인식 capability retrieval

외부 런타임은 SchemaRouter에 워크플로 또는 실행 권한을 넘기지 않고도 명시적인 typed execution state를 capability retrieval에 반영할 수 있습니다.

기존 `retrieve(request, *, k=5)` facade는 stateless 계약과 하위 호환성을 그대로 유지합니다.

## 고정 Top-K 필터링

호스트가 기존 Top-K 순위를 그대로 사용하면서 observable state에 맞지 않는 후보만 제거하려면 `retrieve_state_aware(...)` 를 사용합니다.

```python
from schemarouter import CapabilityFieldContract, TypedExecutionState

eligible = router.retrieve_state_aware(
    "material 조회를 계속해",
    execution_state=TypedExecutionState(...),
    k=5,
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

이 경로는 의도적으로 다음 semantics를 유지합니다.

```text
기존 Top-K -> state eligibility filter
```

필터링으로 빠진 자리를 추가 후보로 채우지는 않습니다.

## Eligible Top-K 재검색 및 backfill

전체 visible ranking에서 실제로 사용 가능한 K개를 채워야 한다면 `reretrieve_state_aware(...)` 를 사용합니다.

```python
eligible = router.reretrieve_state_aware(
    "material 조회를 계속해",
    execution_state=TypedExecutionState(...),
    k=5,
    state_requirements=state_requirements,
    state_preconditions=state_preconditions,
)
```

이 경로는 다음처럼 동작합니다.

```text
visible ranked capability surface
        |
        v
명시적 state requirement / precondition
        |
        v
첫 K개의 eligible candidate
```

초기 상위 후보가 제외되면 K개의 eligible 후보가 채워지거나 visible surface가 소진될 때까지 기존 순위의 다음 후보를 계속 검사합니다.

결과에는 다음이 포함됩니다.

- state filter 전 후보의 `original_rank`;
- eligible 결과 내에서 다시 매긴 `candidate.rank`;
- 제외된 visible 후보와 구조화된 `StateEligibility` 사유;
- 검사한 후보 수 `examined_count` 와 surface 소진 여부.

Registry/availability 정책 때문에 보이지 않는 후보는 backfill 과정에서 새로 노출되지 않으며 exclusion trace에도 나타나지 않습니다.

비동기 API는 `await router.aretrieve_state_aware(...)`, `await router.areretrieve_state_aware(...)` 입니다.

호스트가 이미 `CapabilityRetrieval` 객체를 가지고 있다면 하위 수준의 `filter_retrieval_by_state(...)` 와 `backfill_retrieval_by_state(...)` 도 사용할 수 있습니다.

## State 경계

`state_requirements` 와 `state_preconditions` 는 호스트가 명시적으로 제공하는 계약 메타데이터입니다. SchemaRouter는 route 이름, parameter 이름, 설명, 이전 rank 위치, 문서화되지 않은 payload text 또는 숨겨진 미래 route에서 workflow precondition을 추론하지 않습니다.

선언된 requirement에 필요한 typed state가 없거나 호환되지 않으면 해당 후보는 fail-closed로 제외됩니다. 반대로 state requirement가 선언되지 않은 route는 기존 stateless 동작을 유지합니다.

두 state-aware API 모두 워크플로 선택, capability 실행, transaction commit/rollback, 호스트 상태 변경, retry scheduling, compensation 실행 또는 authorization 확대를 수행하지 않습니다. 정책, availability, 실행, retry, compensation 권한은 계속 호스트 런타임에 있습니다.

# State-aware capability retrieval

External runtime은 SchemaRouter에 workflow/execution authority를 넘기지 않고 일반 retrieval 결과를 typed execution state로 필터링할 수 있습니다.

```python
from schemarouter import filter_retrieval_by_state

eligible = filter_retrieval_by_state(
    retrieval,
    execution_state,
    requirements_by_route=typed_state_requirements,
)
```

`requirements_by_route`는 host가 명시적으로 제공하는 contract metadata입니다. SchemaRouter는 route 이름, parameter 이름, description, 이전 call에서 workflow precondition을 추론하지 않습니다. 선언된 requirement에 필요한 typed state가 없거나 incompatible하면 fail-closed로 제외하고, state requirement가 선언되지 않은 route는 계속 eligible합니다. 생존 candidate 사이의 기존 retrieval ranking은 보존합니다.

이 API는 filtering만 수행합니다. Workflow 선택, capability 실행, state 변경, retry, business transaction 완료 판단은 하지 않습니다.

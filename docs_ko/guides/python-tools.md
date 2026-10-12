# Python 도구

타입이 선언된 Python 함수는 가장 간단한 로컬 연결 방식입니다.

## Callable 등록

```python
from pydantic import BaseModel

from schemarouter import PlanRequest, SchemaRouter, schema_tool


class LookupResult(BaseModel):
    user_id: int
    name: str


@schema_tool(read_only=True)
def lookup_user(user_id: int) -> LookupResult:
    return LookupResult(user_id=user_id, name="Ada")


router = SchemaRouter()
router.add_callable(lookup_user)

result = router.invoke(
    PlanRequest(
        query="user id name",
        arguments={"user_id": 42},
    )
)
```

## 자동으로 도출되는 것

함수의 타입 정보에서 다음 항목을 만듭니다.

- endpoint input JSON Schema
- function signature 기반 required argument
- output JSON Schema
- projection 가능한 top-level response field

Pydantic model과 dataclass output은 runtime validation 전에 JSON-compatible value로 변환됩니다.

## Sync / async

둘 다 지원합니다.

```python
async def lookup_user(user_id: int) -> dict[str, str]:
    ...
```

공통 executor가 반환값이 awaitable이면 알아서 기다립니다.

## 제한

자동 변환에서는 variadic `*args` / `**kwargs`와 positional-only parameter를 받지 않습니다.
이름이 있는 JSON 인자로 안전하게 표현하기 어렵다면 `ToolSpec`을 직접 선언해야 합니다.

## `@schema_tool`과 `add_callable`

`@schema_tool(...)`은 function을 감싸지 않고 로컬 authoring metadata를 저장합니다.
`add_callable(...)`에 명시적으로 넘긴 값이 decorator metadata보다 우선합니다.

`read_only=True`는 실제로 retry-safe한 operation에만 사용하십시오.

## Explicit ToolSpec + trusted invoker

SDK가 안정적인 Python signature/output annotation을 제공하지 않는다면 package 전체를 reflection
하거나 runtime sample에서 schema를 추측하지 말고 contract를 명시적으로 선언합니다.

```python
tool = ToolSpec(
    name="market_lookup",
    provider="yahoo-finance",
    access_mode="sdk",
    endpoints=[...],
)

router.add_bound_tool(
    tool,
    sdk_invoker,
)
```

`ToolSpec`은 모델에 노출되는 전체 계약입니다. Invoker가 사용하는 client object, API key, DB
connection, CLI wrapper 등 신뢰된 전송 상태는 schema에 복사되지 않습니다.

Endpoint-style `invoker(endpoint_name, arguments)`와 call-aware
`invoker.invoke_call(tool_call)`를 모두 지원합니다. 바인딩은 **정확한 tool fingerprint**에
고정되며, 도구를 교체할 때는 레지스트리의 일반적인 **compare-and-swap(CAS) 경계**를 사용합니다.

일반 typed function이면 `add_callable()`, opaque SDK/protocol이면 `add_bound_tool()`을
사용하는 것이 기본 원칙입니다.


```python
invoker(endpoint_name, arguments)
```

```python
invoker.invoke_call(tool_call)
```

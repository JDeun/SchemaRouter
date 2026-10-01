# Python 도구

Typed Python callable은 가장 단순한 로컬 integration 경로입니다.

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

Python type information에서 다음을 만듭니다.

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

Common executor가 필요할 때 await합니다.

## 제한

자동 derivation에서는 variadic `*args` / `**kwargs`, positional-only parameter를 거부합니다.
Named JSON argument로 안전하게 표현하기 어려운 경우 explicit `ToolSpec`을 사용하십시오.

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

`ToolSpec`은 model-visible contract이고 client object, API key, DB connection 같은 trusted
runtime state는 schema로 복사되지 않습니다.

일반 typed function이면 `add_callable()`, opaque SDK/protocol이면 `add_bound_tool()`을
사용하는 것이 기본 원칙입니다.

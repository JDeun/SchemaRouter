# Python tools

Typed Python callables are the simplest local integration path.

## Register a callable

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

## What is derived

SchemaRouter uses Python type information to derive:

- endpoint input JSON Schema;
- required arguments from the function signature;
- output JSON Schema;
- top-level response fields for projection.

Pydantic model and dataclass outputs are converted to JSON-compatible values before runtime output
validation.

## Sync and async functions

Both are supported:

```python
async def lookup_user(user_id: int) -> dict[str, str]:
    ...
```

The common executor awaits the result when necessary.

## Explicit constraints

Variadic `*args` / `**kwargs` and positional-only parameters are rejected by automatic derivation.
Use an explicit `ToolSpec` when the function contract cannot be represented as named JSON arguments.

## Decorator versus add_callable options

`@schema_tool(...)` stores local authoring metadata without wrapping the function. Explicit arguments
to `add_callable(...)` take precedence over decorator metadata.

Use `read_only=True` when it is genuinely safe to retry the operation. Do not label a mutation
read-only merely to enable retry behavior.

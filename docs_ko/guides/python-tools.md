# Python tool

Typed Python callable은 가장 단순한 local integration 경로입니다.

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

## 자동으로 파생되는 항목

SchemaRouter uses Python type information to derive:

- endpoint input JSON Schema;
- required arguments from the function signature;
- output JSON Schema;
- top-level response fields for projection.

Pydantic model and dataclass outputs are converted to JSON-compatible values before runtime output
validation.

## Sync 및 async function

Both are supported:

```python
async def lookup_user(user_id: int) -> dict[str, str]:
    ...
```

The common executor awaits the result when necessary.

## 명시적 제약

Variadic `*args` / `**kwargs` and positional-only parameters are rejected by automatic derivation.
Use an explicit `ToolSpec` when the function contract cannot be represented as named JSON arguments.

## Decorator versus add_callable options

`@schema_tool(...)` stores local authoring metadata without wrapping the function. Explicit arguments
to `add_callable(...)` take precedence over decorator metadata.

Use `read_only=True` when it is genuinely safe to retry the operation. Do not label a mutation
read-only merely to enable retry behavior.

## Explicit ToolSpec + trusted invoker

Some SDKs do not expose stable Python signatures or return annotations. Do not reflect an entire
package or guess a schema from runtime values. Declare the capability explicitly and bind trusted
local code:

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

The supplied `ToolSpec` remains the complete model-visible contract. The invoker may capture a
client object, API key, database connection, CLI wrapper, or other trusted transport state; none of
that state is copied into the schema.

Both endpoint-style invokers:

```python
invoker(endpoint_name, arguments)
```

and call-aware invokers:

```python
invoker.invoke_call(tool_call)
```

are supported. Bindings are pinned to the exact tool fingerprint, and replacement uses the normal
registry compare-and-swap boundary.

Prefer `add_callable()` when a normal typed Python function is available. Use
`add_bound_tool()` when the external SDK/protocol surface cannot be safely introspected.

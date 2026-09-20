# Model-assisted analysis

The default planner can work offline with `KeywordAnalyzer`. Use `ModelQueryAnalyzer` when natural
language needs richer extraction of tools, endpoints, arguments, fields, or evidence requirements.

## Provider-neutral callable

SchemaRouter does not require a specific LLM SDK.

```python
from schemarouter import ModelQueryAnalyzer, SchemaRouter

async def model(payload: dict) -> dict:
    # Bridge to your provider's structured-output API.
    return {
        "preferred_tools": ["users_api"],
        "preferred_endpoints": ["users_api.get_user"],
        "arguments": {"user_id": "42"},
        "fields": ["name", "email"],
        "concepts": [],
        "evidence": {},
    }

router = SchemaRouter(
    analyzer=ModelQueryAnalyzer(model),
)
```

The payload contains the current catalog and a response schema.

## Model output is not executable

The analyzer validates the response shape, then projects it back onto the current registry.

```text
model output
 -> strict shape validation
 -> known tool?
 -> known endpoint?
 -> declared argument?
 -> declared field?
 -> deterministic planner
```

Unknown or invented schema elements cannot become executable calls.

Explicit arguments supplied by the application have higher priority than model-produced arguments.

## Remote descriptions are untrusted

OpenAPI descriptions, MCP annotations, and documentation text can contain prompt injection or
misleading instructions. The analyzer prompt explicitly treats catalog descriptions as untrusted
data.

Do not put credentials in catalog descriptions or model-visible arguments.

## Sync versus async

`ModelQueryAnalyzer` is async-capable. If an async analyzer is attached, use `aplan()`,
`ainvoke()`, or the other async execution surfaces.

Calling the synchronous planning surface with an async analyzer fails explicitly instead of silently
leaking an un-awaited coroutine.

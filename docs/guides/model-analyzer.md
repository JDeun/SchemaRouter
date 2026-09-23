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

The callable may be backed by the same hosted model client the application already uses. For
example, an application can bridge GPT, Gemini, Claude, or another provider's structured-output API
without adding that provider SDK to SchemaRouter itself.

This is distinct from a bounded `DecisionBackend`:

| Surface | Model sees | Model may return | SchemaRouter does next |
| --- | --- | --- | --- |
| `ModelQueryAnalyzer` | query + schema catalog + response contract | tool/endpoint preferences, declared arguments/fields, concepts, evidence request | sanitizes everything against the current registry, then runs deterministic planning |
| `CallableDecisionBackend` | query + finite already-authorized option IDs | only bounded option selections | validates IDs/counts, then continues the existing planner |

Neither surface turns the cloud model into an agent runtime. Tool execution, policy, schema
fingerprints, and authority remain local to SchemaRouter.

For a supported OpenAPI discriminated request body, the catalog contains one `body` parameter with
the original composed schema. A hosted model can therefore return:

```json
{
  "preferred_tools": ["pets"],
  "preferred_endpoints": ["pets.create_pet"],
  "arguments": {
    "body": {
      "kind": "dog",
      "name": "Mong",
      "breed": "retriever"
    }
  },
  "fields": ["id"],
  "concepts": [],
  "evidence": {}
}
```

SchemaRouter still validates that object locally against the endpoint input schema before any HTTP
request is allowed.

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

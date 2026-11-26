# OpenAPI agent boundary

Use this pattern when a broader agent should reason conversationally but tool execution must stay
schema-constrained. The agent provides an explicit request and arguments; the product router does not invoke a separate catalog-based model analyzer.

```python
from schemarouter import (
    ExecutionPolicy,
    PlanRequest,
    SchemaRouter,
)


router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
    policy=ExecutionPolicy(
        allow_mutations=False,
        allow_destructive=False,
    ),
)

request = PlanRequest(
    query="Find user 42 and return only the name and email",
    arguments={"user_id": "42"},
)

results = await router.ainvoke(request)
```

## Why this boundary works

The surrounding agent can still decide **when** to ask SchemaRouter for a tool result. Once it does,
the executable operation is constrained by:

- the current imported schema;
- explicit caller arguments;
- local execution policy;
- schema fingerprint checks;
- input/output validation.

This keeps model reasoning flexible without making the transport contract equally flexible.

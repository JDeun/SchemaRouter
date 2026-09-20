# Execution policy

`ExecutionPolicy` is the trusted local side-effect gate.

Planning may identify a relevant mutation. That does not mean the mutation is authorized.

## Default behavior

The default policy is intentionally conservative for remote capabilities:

- normal local/manual contracts can execute;
- known OpenAPI mutations are blocked unless enabled;
- destructive operations are blocked unless enabled;
- unclassified remote MCP operations are blocked unless enabled.

## Configure local authority

```python
from schemarouter import ExecutionPolicy, SchemaRouter

router = SchemaRouter(
    policy=ExecutionPolicy(
        allow_mutations=True,
        allow_destructive=False,
        allow_unclassified_remote=False,
    )
)
```

Only trusted application code should construct this policy.

## Why remote metadata cannot grant permission

A remote server controls its own descriptions and annotations. Allowing those fields to set local
execution authority would let the capability provider authorize itself.

SchemaRouter therefore keeps remote metadata descriptive and local policy authoritative.

## Approval versus policy

Documentation-derived tools have two independent gates:

```text
grounded proposal
 -> explicit approve_proposal()
 -> registered/bound tool
 -> ExecutionPolicy
 -> execute
```

Approval decides whether the inferred contract may enter the executable registry. Policy decides
whether the specific side effect is permitted at runtime.

## Destructive operations

DELETE-like operations are marked destructive when the adapter can determine that classification.
Set `allow_destructive=True` only when the surrounding application has appropriate authorization,
audit, and confirmation semantics.

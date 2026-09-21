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

## Per-call approval

Policy permission and human/application approval are separate gates.

```python
from schemarouter import ExecutionPolicy, SchemaRouter

async def approve(tool, endpoint, call) -> bool:
    return await my_approval_service.check(
        tool=tool.key,
        endpoint=endpoint.name,
    )

router = SchemaRouter(
    policy=ExecutionPolicy(
        allow_mutations=True,
        approval_mode="non_read_only",
    ),
    approval_callback=approve,
)
```

`approval_mode` accepts:

- `never` — no per-call callback, the default;
- `non_read_only` — approval for mutating and unclassified operations;
- `all` — approval before every call.

If approval is required and no callback exists, the call fails closed. Callback exceptions also fail
closed. Only the literal boolean `True` approves a call.

The callback exists only in trusted local code. It is not serializable planner input and cannot be
created by remote metadata or a model.

## Per-run execution budgets

```python
from schemarouter import ExecutionBudget, RunConfig

config = RunConfig(
    budget=ExecutionBudget(
        max_tool_calls=4,
        max_attempts=6,
        max_remote_attempts=4,
        max_elapsed_seconds=15,
        max_cost_units=3.0,
        per_tool_calls={"materials": 2},
        cost_units={
            "materials.search": 0.5,
            "papers.search": 1.0,
            "*": 0.25,
        },
    )
)

results = await router.ainvoke(request, config=config)
```

Semantics are deterministic:

- logical tool calls are counted once per planned call;
- every real invoker attempt counts, including retries;
- remote attempts count separately;
- cost units are charged per attempt;
- operation-specific cost overrides tool-specific cost, which overrides `"*"`;
- the same budget state is shared by all calls in one plan;
- async invocations are interrupted when the wall-clock budget expires.

Batch APIs treat each input invocation as its own run and therefore its own budget.

Budgets are local enforcement, not billing. Cost units are application-defined weights.

## Retry interaction

Read-only retries remain the default. If a call is retried, each retry consumes attempt, remote, and
cost budgets before the network/tool invocation occurs.

A budget refusal is not retried.

## Why remote metadata cannot grant permission

A remote server controls its own descriptions and annotations. Allowing those fields to set local
execution authority would let the capability provider authorize itself.

SchemaRouter therefore keeps remote metadata descriptive and local policy authoritative.

## Approval versus documentation proposal approval

Documentation-derived tools have distinct gates:

```text
grounded proposal
 -> explicit approve_proposal()
 -> registered/bound tool
 -> ExecutionPolicy
 -> optional per-call approval
 -> execution budget
 -> execute
```

Proposal approval decides whether an inferred contract may enter the registry. Runtime approval
decides whether this particular call may execute now.

## Destructive operations

DELETE-like operations are marked destructive when the adapter can determine that classification.
Set `allow_destructive=True` only when the surrounding application has appropriate authorization,
audit, confirmation, and rollback semantics.

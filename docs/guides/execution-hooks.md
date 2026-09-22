# Trusted execution hooks

SchemaRouter supports ordered local callbacks immediately around validated tool execution.

Hooks are intended for organization-specific audit, policy integration, metrics, local vetoes, and
other trusted middleware that should not become part of the model-visible tool contract.

## Configure hooks

```python
from schemarouter import ExecutionHooks, SchemaRouter


def before(tool, endpoint, call):
    audit_call(call)


def after(tool, endpoint, call, result):
    audit_result(result)


router = SchemaRouter(
    execution_hooks=ExecutionHooks(
        before_call=[before],
        after_call=[after],
    )
)
```

Both sync and async callables are supported. Hooks run in declaration order. Async hooks are
bounded by the remaining `ExecutionBudget.max_elapsed_seconds` budget; synchronous hooks cannot be
preempted, but elapsed time is checked immediately after they return.

## Execution order

For one logical tool call, the relevant boundary is:

```text
plan
 -> current schema + policy validation
 -> elapsed-budget clock
 -> optional trusted approval
 -> schema/binding revalidation
 -> budget logical-call accounting
 -> before hooks
 -> schema/binding revalidation
 -> invoker attempts / retries
 -> raw output JSON Schema validation
 -> field projection
 -> after hooks
 -> ToolResult
```

A before hook therefore cannot bypass schema validation, execution policy, approval, or binding
checks. Because a hook may await, SchemaRouter refreshes executable state after all before hooks
finish.

## Snapshot-only contract

Hooks receive deep copies of the models supplied to them.

A before hook receives:

- `ToolSpec`;
- `EndpointSpec`;
- `ToolCall`.

An after hook additionally receives the final projected `ToolResult`.

Mutating those objects does not mutate the executable call, registry schema, or result returned to
the caller.

Hooks must return `None`. Any other return value raises `ExecutionHookError`. This deliberately
avoids an implicit transformation API that could alter arguments, fields, schemas, or execution
authority.

## Failure behavior

Hook failures are fail-closed.

- A failing before hook prevents the invoker from running.
- A failing after hook withholds the result from the caller.
- Hook failures are never treated as retryable tool failures.
- In particular, an after-hook failure does **not** repeat a successful read-only invocation.

A hook can deliberately veto execution by raising an exception. SchemaRouter wraps ordinary hook
exceptions in `ExecutionHookError`. Elapsed-budget expiration remains an
`ExecutionBudgetExceededError` and is not rewritten as a hook failure.

## Privacy

Execution hooks are trusted local code, not redacted telemetry.

Before hooks receive the validated call arguments. After hooks receive the projected result payload.
Do not register third-party or remote callbacks as hooks unless they are trusted to receive that
data.

For privacy-preserving observability across less-trusted sinks, prefer the redacted `RunEvent`
stream or the OpenTelemetry exporter.

## Relationship to approval

Approval and execution hooks serve different purposes.

- Approval is an explicit boolean authority gate controlled by `ExecutionPolicy.approval_mode`.
- Hooks are ordered middleware around already-authorized execution and may only observe or fail
  closed.

Hooks cannot approve an operation that policy or the approval callback rejected.

## Direct executor use

```python
executor = RegistryExecutor(
    registry,
    hooks=ExecutionHooks(
        before_call=[before],
        after_call=[after],
    ),
)
```

The same contract applies whether hooks are configured through `SchemaRouter` or directly on
`RegistryExecutor`.

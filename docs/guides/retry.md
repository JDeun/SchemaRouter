# Retry policy

Retries are applied at the trusted executor boundary.

## Configure retries

```python
from schemarouter import RetryPolicy, RunConfig

config = RunConfig(
    retry=RetryPolicy(
        max_attempts=3,
        initial_backoff_seconds=0.25,
        backoff_multiplier=2.0,
        max_backoff_seconds=5.0,
    )
)

result = await router.ainvoke(request, config=config)
```

## Read-only by default

Automatic retry is enabled only when the endpoint is explicitly classified as `read_only=True`.

This prevents a transient failure from accidentally repeating a write operation.

```text
read_only=True
 -> max_attempts may apply

read_only=False or unknown
 -> one attempt by default
```

Trusted local code can set `retry_non_read_only=True`, but that is an explicit idempotency decision.

## What is not retryable

Schema contract violations fail immediately.

Examples:

- invalid tool output;
- an output enum/type violation;
- invalid current input schema;
- stale schema fingerprint;
- stale invoker binding;
- policy rejection.

Retrying these would hide a deterministic correctness problem rather than recover a transient
transport failure.

## Choosing a policy

Keep the default `max_attempts=1` unless the underlying operation and transport semantics justify
automatic retry.

For remote HTTP APIs, consider whether the endpoint itself is idempotent in addition to the HTTP
method or schema classification.

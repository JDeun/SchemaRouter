# Retry 정책

retry는 trusted executor 경계에서 적용됩니다.

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
```

## 기본은 read-only

자동 retry는 endpoint가 명시적으로 `read_only=True`일 때만 활성화됩니다. transient failure 때문에 write operation이 반복되는 것을 막기 위한 것입니다. trusted local code가 `retry_non_read_only=True`를 지정할 수 있지만 이는 명시적인 idempotency 판단입니다.

## Retry하지 않는 실패

schema contract 위반은 즉시 실패합니다. trusted invoker도 같은 호출을 반복해 안전하게 복구할 수 없는 경우 `NonRetryableInvocationError`를 발생시킬 수 있습니다.

invalid tool output, output enum/type violation, invalid current input schema, stale schema fingerprint/binding, policy rejection 등 deterministic correctness 문제는 retry로 숨기지 않습니다.

내장 OpenAPI/OPTIMADE HTTP invoker는 408, 425, 429, 500, 502, 503, 504를 retryable status로 분류하고 다른 HTTP error는 즉시 실패합니다. oversized response, malformed declared JSON, invalid OPTIMADE success shape도 fail-fast입니다.

## 정책 선택

underlying operation과 transport semantics가 자동 retry를 정당화하지 않는다면 기본 `max_attempts=1`을 유지하세요. backoff도 run wall-clock budget을 소비하며 요청 delay가 `ExecutionBudget.max_elapsed_seconds`를 넘으면 남은 budget 경계에서 중지합니다.

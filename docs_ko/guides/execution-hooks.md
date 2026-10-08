# Trusted execution hooks

SchemaRouter는 검증된 tool execution 직전·직후에 순서가 보장되는 local callback을 지원합니다.

hook은 조직별 audit, policy integration, metric, local veto 등 model-visible tool contract에 포함되면 안 되는 trusted middleware를 위한 기능입니다.

## Hook 설정

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

sync/async callable을 모두 지원하며 hook은 선언 순서대로 실행됩니다. async hook은 남은 `ExecutionBudget.max_elapsed_seconds` budget으로 제한됩니다. synchronous hook은 중간에 preempt할 수 없지만 반환 직후 elapsed time을 검사합니다.

## 실행 순서

하나의 logical tool call에서 관련 boundary는 다음과 같습니다:

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
 -> field projection + ToolResult construction
 -> after hooks
 -> return ToolResult
```

before hook은 schema validation, execution policy, approval, binding check를 우회할 수 없습니다. hook이 await할 수 있으므로 SchemaRouter는 모든 before hook 종료 후 executable state를 갱신합니다.

## Snapshot-only contract

hook은 전달된 model의 deep copy를 받습니다.

before hook은 다음을 받습니다:

- `ToolSpec`;
- `EndpointSpec`;
- `ToolCall`.

after hook은 여기에 최종 projected `ToolResult`도 받습니다.

이 object들을 변경해도 executable call, registry schema, caller에게 반환되는 result는 변경되지 않습니다.

hook은 `None`을 반환해야 합니다. before hook이 non-`None`을 반환하면 `ExecutionHookError`, after hook이 non-`None`을 반환하면 외부 operation과 result validation이 이미 성공했으므로 `PostInvocationHookError`가 발생합니다. 이를 통해 argument, field, schema, execution authority를 바꿀 수 있는 암묵적 transformation API를 방지합니다.

## 실패 동작

hook failure는 fail-closed되지만 pre/post-invocation failure의 semantic은 서로 다릅니다.

- before hook failure는 invoker 실행을 막고 `ExecutionHookError`로 노출됩니다.
- after hook failure는 정상 return path를 차단하지만 성공한 projected `ToolResult`는 `PostInvocationHookError.result`에 보존됩니다.
- `PostInvocationHookError.execution_succeeded`는 항상 `True`입니다.
- post-invocation failure는 trusted code가 non-read-only endpoint의 retry를 명시적으로 활성화했더라도 non-retryable입니다. 따라서 audit/metrics hook 실패 때문에 성공한 mutation이 반복되지 않습니다.
- event stream은 성공한 operation을 `tool.end`로 기록한 뒤 `stage="post_invocation_hook"`인 `run.error`를 노출하며, 해당 operation을 `tool.error`로 다시 쓰지 않습니다.

before-hook elapsed-budget expiration은 계속 `ExecutionBudgetExceededError`입니다. tool이 validated/projected result를 성공적으로 생성한 이후 after hook에서 exception, cancellation, invalid return, elapsed-budget failure가 발생하면 `PostInvocationHookError`로 감싸 caller가 tool success와 post-processing failure를 구분할 수 있게 합니다.

## Privacy

execution hook은 trusted local code이며 redacted telemetry가 아닙니다.

before hook은 validated call argument를 받고 after hook은 projected result payload를 받습니다. 해당 데이터를 받아도 신뢰할 수 있는 경우가 아니라면 third-party/remote callback을 hook으로 등록하지 않습니다.

신뢰도가 낮은 sink에서도 privacy-preserving observability가 필요하면 redacted `RunEvent` stream 또는 OpenTelemetry exporter를 사용합니다.

## Approval과의 관계

approval과 execution hook은 서로 다른 목적을 가집니다.

- approval은 `ExecutionPolicy.approval_mode`가 제어하는 명시적 boolean authority gate입니다.
- hook은 이미 authorize된 execution 주변의 ordered middleware이며 관찰하거나 fail-closed할 수만 있습니다.

hook은 policy 또는 approval callback이 거부한 operation을 승인할 수 없습니다.

## Direct executor 사용

```python
executor = RegistryExecutor(
    registry,
    hooks=ExecutionHooks(
        before_call=[before],
        after_call=[after],
    ),
)
```

hook을 `SchemaRouter`에서 설정하든 `RegistryExecutor`에 직접 설정하든 동일한 contract가 적용됩니다.

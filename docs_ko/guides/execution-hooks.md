# Trusted execution hook

SchemaRouter는 검증된 tool 실행 직전/직후에 순서가 보장되는 local callback을 지원합니다. 조직별 audit, policy integration, metric, local veto 등 model-visible tool contract에 들어가면 안 되는 trusted middleware용입니다.

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

sync/async callable을 모두 지원하고 선언 순서로 실행합니다. async hook은 남은 execution budget으로 제한됩니다.

## 실행 순서

schema/policy validation → budget → optional approval → schema/binding revalidation → logical-call accounting → before hook → 재검증 → invocation/retry → raw output validation → projection 및 `ToolResult` 생성 → after hook → `ToolResult` 반환 순입니다.

before hook은 validation/policy/approval/binding을 우회할 수 없습니다.

## Snapshot-only contract

hook은 전달 모델의 deep copy를 받습니다. 이를 수정해도 executable call, registry schema, caller에게 반환되는 result는 바뀌지 않습니다. hook은 반드시 `None`을 반환해야 합니다. before hook의 비-`None` 반환은 `ExecutionHookError`, after hook의 비-`None` 반환은 외부 실행이 이미 성공한 뒤이므로 `PostInvocationHookError`입니다.

## 실패 동작

hook 실패는 fail-closed이지만 실행 전/후의 의미를 구분합니다. before hook 실패는 invoker 실행을 막고 `ExecutionHookError`로 노출됩니다. after hook 실패는 정상 반환 경로를 중단하지만 성공한 projected `ToolResult`를 `PostInvocationHookError.result`에 보존하며 `execution_succeeded=True`를 명시합니다. 이 오류는 non-retryable이므로 non-read-only retry를 명시적으로 허용한 경우에도 성공한 mutation을 hook 오류 때문에 반복하지 않습니다. event stream은 이 상황을 `tool.error`로 바꾸지 않고 `tool.end`를 기록한 뒤 `run.error(stage="post_invocation_hook")`로 후처리 실패를 별도로 노출합니다. before hook에서의 elapsed-budget 초과는 기존처럼 `ExecutionBudgetExceededError`이고, tool 성공 이후 after hook에서 발생한 예외·취소·잘못된 반환·budget 초과는 `PostInvocationHookError`로 구분됩니다.

## Privacy와 approval

execution hook은 redacted telemetry가 아니라 trusted local code이며 validated argument/result를 볼 수 있습니다. 덜 신뢰되는 sink에는 redacted `RunEvent` 또는 OpenTelemetry exporter를 사용하세요.

approval은 명시적 boolean authority gate이고 hook은 이미 허가된 실행 주변 middleware입니다. hook이 policy/approval callback이 거부한 operation을 승인할 수 없습니다.

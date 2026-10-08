# 신뢰 가능한 실행 훅

SchemaRouter는 검증된 도구 실행 직전과 직후에 순서대로 로컬 콜백을 실행할 수 있습니다.

훅은 조직별 감사, 정책 연동, 지표 수집, 로컬 실행 거부 및 모델에 노출되는 도구 계약에 포함되어서는 안 되는 기타 신뢰된 미들웨어를 위해 설계했습니다.

## 훅 설정

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

동기·비동기 callable을 모두 지원하며 선언된 순서대로 실행합니다. 비동기 훅은 남아 있는 `ExecutionBudget.max_elapsed_seconds` 예산으로 제한합니다. 동기 훅은 실행 도중 선점 중단할 수 없지만, 반환한 직후 경과 시간을 확인합니다.

## 실행 순서

논리적 도구 호출 하나의 주요 실행 경계는 다음과 같습니다.

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

실행 전 훅으로 스키마 검증, 실행 정책, 승인 또는 바인딩 검사를 우회할 수 없습니다. 훅이 `await`를 통해 대기할 수 있으므로 모든 실행 전 훅이 끝난 이후 SchemaRouter가 실행 가능 상태를 다시 확인합니다.

## 스냅샷 전용 계약

훅은 자신에게 전달된 모델의 깊은 복사본을 받습니다.

실행 전 훅에 전달되는 항목은 다음과 같습니다.

- `ToolSpec`
- `EndpointSpec`
- `ToolCall`

실행 후 훅에는 최종 필드 투영이 적용된 `ToolResult`가 추가됩니다.

이 객체들을 수정하더라도 실제 실행할 호출, 레지스트리 스키마, 호출자에게 반환할 결과는 변경되지 않습니다.

훅은 반드시 `None`을 반환해야 합니다. 실행 전 훅이 `None` 이외의 값을 반환하면 `ExecutionHookError`가 발생합니다. 실행 후 훅이 `None` 이외의 값을 반환하면 외부 작업과 결과 검증은 이미 성공한 상태이므로 `PostInvocationHookError`가 발생합니다. 이는 인자·필드·스키마·실행 권한을 바꿀 수 있는 암묵적 변환 API가 생기는 것을 막기 위한 설계입니다.

## 실패 동작

훅 실패는 안전하게 닫히는(fail-closed) 방식으로 처리하지만 호출 전과 호출 후의 의미가 다릅니다.

- **실행 전 훅 실패:** invoker 실행을 막고 `ExecutionHookError`를 반환합니다.
- **실행 후 훅 실패:** 일반적인 반환 경로를 중단하지만 성공한 투영 결과 `ToolResult`를 `PostInvocationHookError.result`에 보존합니다.
- `PostInvocationHookError.execution_succeeded`는 언제나 `True`입니다.
- 실행 후 훅의 실패는 재시도하지 않습니다. 신뢰된 코드가 읽기 전용이 아닌 엔드포인트에 명시적 재시도를 활성화한 경우에도 마찬가지입니다. 따라서 감사나 지표 훅이 실패했다는 이유로 이미 성공한 데이터 변경 작업을 반복하지 않습니다.
- 이벤트 스트림에는 성공한 작업을 `tool.end`로 기록한 뒤 `stage="post_invocation_hook"`인 `run.error`를 노출합니다. 해당 작업의 결과를 `tool.error`로 바꾸지 않습니다.

실행 전 훅이 경과 시간 예산을 초과하면 `ExecutionBudgetExceededError`가 유지됩니다. 도구에서 검증과 투영까지 완료된 결과를 성공적으로 생성한 뒤 실행 후 훅에서 예외·취소·유효하지 않은 반환·시간 초과가 발생하면 `PostInvocationHookError`로 감쌉니다. 이를 통해 호출자는 **도구 실행 성공과 후처리 실패를 구분**할 수 있습니다.

## 개인정보 보호

실행 훅은 신뢰된 로컬 코드이며 민감 정보를 가리는 텔레메트리가 아닙니다.

실행 전 훅은 검증된 호출 인자를 받습니다. 실행 후 훅은 투영된 결과 페이로드를 받습니다. 해당 데이터를 볼 권한이 없는 서드파티나 원격 콜백은 훅으로 등록하지 마십시오.

신뢰도가 낮은 수신 대상으로 개인정보를 보호하며 관측 데이터를 전송하려면 민감 정보를 가린 `RunEvent` 스트림이나 OpenTelemetry exporter를 사용하십시오.

## 승인 기능과의 관계

승인과 실행 훅은 목적이 다릅니다.

- **승인:** `ExecutionPolicy.approval_mode`로 제어하는 명시적인 불리언 권한 게이트입니다.
- **훅:** 이미 허가된 실행의 전후에서 동작하는 순서 있는 미들웨어이며, 관찰하거나 안전하게 실행을 중단할 수만 있습니다.

훅은 정책 또는 승인 콜백이 거부한 작업을 승인할 수 없습니다.

## 실행기 직접 사용

```python
executor = RegistryExecutor(
    registry,
    hooks=ExecutionHooks(
        before_call=[before],
        after_call=[after],
    ),
)
```

`SchemaRouter`를 통해 훅을 구성하든 `RegistryExecutor`에 직접 설정하든 동일한 계약이 적용됩니다.

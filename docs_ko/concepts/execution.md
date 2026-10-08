# 실행과 신뢰 경계

실행 단계는 계획 단계보다 더 엄격한 조건을 적용합니다.

## 실행 파이프라인

```text
ToolCall
  -> current endpoint lookup
  -> schema fingerprint check
  -> argument allowlist
  -> required-argument recomputation
  -> input JSON Schema validation
  -> execution policy
  -> invoker binding check
  -> trusted invocation
  -> raw output JSON Schema validation
  -> field projection
  -> ToolResult
```

## 계획은 권한이 아닙니다

계획에는 데이터 변경 작업이 기술될 수 있지만, 그렇다고 해당 작업을 실행할 권한이 있는 것은 아닙니다. 부작용 발생 여부에 관한 권한 기준은 로컬 `ExecutionPolicy`입니다.

원격 OpenAPI 설명, MCP 주석, 모델 출력으로는 정책 권한을 높일 수 없습니다.

## 자격 증명은 모델 인자에 포함하지 않습니다

OpenAPI에서는 두 종류의 헤더를 구분합니다.

- `schema_headers`: OpenAPI 문서를 가져오는 동안에만 사용합니다.
- `trusted_headers`: 런타임의 신뢰된 전송 계층에서만 삽입합니다.

민감한 런타임 헤더는 도구 파라미터로 노출하지 않습니다.

## 네트워크 출처

OpenAPI 런타임 호출은 승인된 API 출처(origin)로 제한합니다. 다른 출처를 가리키는 `servers` 선언은 신뢰된 로컬 코드가 명시적인 기본 URL을 제공하기 전까지 설명용 데이터일 뿐입니다.

스키마 및 문서 리디렉션도 원래 출처 안으로 제한합니다.

## 런타임 검증

입력은 invoker 호출 직전에 검증합니다. 구조화된 원시 출력은 invoker 호출 직후, 그리고 **응답 필드 투영을 하기 전에** 검증합니다.

따라서 요청하지 않은 필드가 잘못돼 응답 전체가 유효하지 않은 경우, 필드 투영으로 오류를 감출 수 없습니다.

## 오류 범주

SchemaRouter는 호출자가 재시도 가능 여부와 후속 조치를 판단할 수 있도록 오류 유형을 구분합니다.

- `PlanningError`
- `PlanValidationError`
- `SchemaValidationError`
- `PolicyViolationError`
- `SchemaDriftError`
- `BindingDriftError`
- `ExecutionError`
- `SchemaSourceError`

스키마 계약을 위반한 작업은 자동으로 재시도하지 않습니다.

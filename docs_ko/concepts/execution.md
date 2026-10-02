# 실행과 신뢰 경계

실행은 planning보다 더 엄격합니다.

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

## Plan은 권한이 아닙니다

plan이 mutation을 기술할 수는 있어도 실제 수행 권한까지 부여하는 것은 아닙니다. side effect에 대한 최종 권한은 로컬 `ExecutionPolicy`에 있습니다.

원격 OpenAPI description, MCP annotation, model output은 policy permission을 높일 수 없습니다.

## Credential은 모델 argument와 분리합니다

OpenAPI는 다음을 구분합니다.

- `schema_headers`: OpenAPI 문서를 가져올 때만 사용
- `trusted_headers`: runtime transport에서만 주입

민감한 runtime header는 tool parameter로 노출되지 않습니다.

## Network origin

OpenAPI runtime call은 승인된 API origin으로 제한됩니다. cross-origin `servers` 선언은 신뢰된 로컬 코드가 명시적 base URL을 제공하기 전까지 설명 정보일 뿐입니다.

schema와 documentation redirect도 원래 origin으로 제한됩니다.

## Runtime validation

input은 invocation 직전에 검증합니다. raw structured output은 invocation 직후, response-field projection **전에** 검증합니다.

따라서 projection으로 잘못된 미요청 field를 숨겨 malformed response를 정상처럼 만들 수 없습니다.

## 오류 범주

호출자가 retry 가능 여부와 대응 방식을 판단할 수 있도록 실패 유형을 구분합니다.

- `PlanningError`
- `PlanValidationError`
- `SchemaValidationError`
- `PolicyViolationError`
- `SchemaDriftError`
- `BindingDriftError`
- `ExecutionError`
- `SchemaSourceError`

schema contract 위반은 자동 retry하지 않습니다.

# 보안 위협 모델

SchemaRouter는 remote schema, documentation, model output, tool result를 신뢰 경계 밖의 입력으로 취급합니다. 핵심 보안 목표는 이 입력이 credential, execution origin, side-effect permission, schema truth를 조용히 바꾸지 못하게 하는 것입니다.

주요 방어선은 credential과 model argument 분리, same-origin/approved-origin network binding, bounded response/schema reads, redirect 제한, current schema/tool fingerprint, binding drift 검사, input/raw-output JSON Schema validation, local ExecutionPolicy/approval/budget, read-only 기본 retry, plugin allowlist, payload-redacted telemetry입니다.

SSRF 관점에서 SchemaRouter는 local/private endpoint를 의도적으로 지원하므로 untrusted end user가 URL을 직접 제출하는 hosted application은 자체 URL admission/egress policy를 추가해야 합니다. human-readable documentation은 grounded proposal까지만 만들고 explicit approval 전에는 executable하지 않습니다.

persistent SQLite에는 schema/catalog 또는 validated event를 저장하지만 credential/invoker를 직렬화하지 않습니다. plugin/hook은 명시적으로 로드한 trusted local Python code로 취급합니다. 보안 defect는 compatibility보다 우선해 fail-closed 수정할 수 있습니다.

## 인가 감사 전달

인가 결정과 audit sink 전달은 분리된 보안 계층입니다. `authorization_audit_hook`에는
principal claim이나 trusted-filter 값이 아닌 privacy-safe 결정 메타데이터만 전달됩니다.

기본 `authorization_audit_delivery_mode`는 `"best_effort"`입니다. sink 장애는
`router.authorization_audit_delivery_status()`에 기록되며 allow 결정을 실행 실패로
바꾸거나 deny 결정을 sink 예외로 가리지 않습니다.

감사 이벤트의 필수 전달이 필요한 환경은 `"strict"`를 명시할 수 있습니다. strict 모드는
audit sink가 반드시 구성되어야 하며, allow된 호출 전에 전달이 실패하면
`AuthorizationAuditDeliveryError`로 fail-closed 합니다. 원래 결정이 deny였다면 deny
효과와 기존 `PolicyViolationError`를 별도로 보존합니다. Run trace에는 sink 예외 문자열이나
principal 데이터 대신 전달 실패 여부와 allow/deny 효과만 남습니다.

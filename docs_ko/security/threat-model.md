# 보안 위협 모델

SchemaRouter는 remote schema, documentation, model output, tool result를 신뢰 경계 밖의 입력으로 취급합니다. 핵심 보안 목표는 이 입력이 credential, execution origin, side-effect permission, schema truth를 조용히 바꾸지 못하게 하는 것입니다.

주요 방어선은 credential과 model argument 분리, same-origin/approved-origin network binding, bounded response/schema reads, redirect 제한, current schema/tool fingerprint, binding drift 검사, input/raw-output JSON Schema validation, local ExecutionPolicy/approval/budget, read-only 기본 retry, plugin allowlist, payload-redacted telemetry입니다.

SSRF 관점에서 SchemaRouter는 local/private endpoint를 의도적으로 지원하므로 untrusted end user가 URL을 직접 제출하는 hosted application은 자체 URL admission/egress policy를 추가해야 합니다. human-readable documentation은 grounded proposal까지만 만들고 explicit approval 전에는 executable하지 않습니다.

persistent SQLite에는 schema/catalog 또는 validated event를 저장하지만 credential/invoker를 직렬화하지 않습니다. plugin/hook은 명시적으로 로드한 trusted local Python code로 취급합니다. 보안 defect는 compatibility보다 우선해 fail-closed 수정할 수 있습니다.

# Execution policy

`ExecutionPolicy`는 tool schema나 model output과 독립적인 trusted local authority입니다. read-only/mutating/destructive/unclassified remote operation에 대한 기본값과 operation-scoped allow/deny/approval rule을 정의합니다.

remote annotation은 권한을 높일 수 없고 plan도 권한이 아닙니다. policy는 invocation 직전에 current endpoint에 대해 다시 평가되며 approval callback, execution budget, schema/binding validation과 함께 fail-closed 경계를 구성합니다.

production에서는 필요한 최소 권한만 허용하고 destructive/mutation은 명시적으로 분류·승인하세요. 조직별 정책 engine은 이 local boundary 뒤에 adapter/hook 형태로 연결해야 하며 underlying transport를 직접 우회해서는 안 됩니다.

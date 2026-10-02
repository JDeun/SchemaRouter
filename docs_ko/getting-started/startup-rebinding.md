# 영속 registry의 시작 시 재바인딩

`SQLiteRegistry`는 capability contract를 영속화하지만 살아 있는 실행 권한은 저장하지 않습니다. credential, HTTP client, SDK object, subprocess handle, MCP factory와 기타 runtime state는 의도적으로 데이터베이스에 저장하지 않습니다.

프로세스가 재시작되면 registry를 다시 열고 trusted binding을 명시적으로 조정합니다.

```python
from schemarouter import SchemaRouter, SQLiteRegistry, TrustedBindingConfig

registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)

def resolve(tool):
    if tool.key == "materials":
        return TrustedBindingConfig(
            trusted_headers={"Authorization": "Bearer ..."},
        )
    if tool.key == "internal_sdk":
        return TrustedBindingConfig(invoker=my_process_local_invoker)
    return None

report = router.rehydrate_bindings(resolve, strict=True)
assert not report.unready
```

resolver는 분리된 ToolSpec snapshot을 받습니다. SchemaRouter는 credential이나 live object를 registry state에 다시 기록하지 않습니다.

## 내장 재구성

SchemaRouter는 영속화된 비밀 정보가 아닌 provenance를 이용해 다음 trusted invoker를 재구성할 수 있습니다.

- OpenAPI: 저장된 승인 base URL 또는 명시적인 trusted `base_url`
- GraphQL: 승인된 endpoint/source URL
- OData: 승인된 service URL
- OpenRPC: 승인된 base URL이 있거나 애플리케이션이 제공한 경우
- OPTIMADE: 저장된 versioned API base
- 선언형 HTTP/JSON tool: 승인된 base URL
- Streamable HTTP MCP: 저장된 source URL과 process-local trusted header

일부 실행 권한은 안전하게 직렬화할 수 없으므로 다시 제공해야 합니다.

- MCP stdio/custom/in-process transport는 호출자 소유 bound factory와 일치하는 저장된 transport fingerprint가 필요합니다.
- Python capability는 원래 callable이 필요합니다.
- LangChain/LlamaIndex capability는 원래 framework tool object가 필요합니다.
- private SDK/custom adapter는 별도의 신뢰된 로컬 binding layer를 제공하지 않는 한 호출자 소유 invoker가 필요합니다.

## Reconciliation 상태

각 항목은 다음 중 하나로 보고됩니다.

- `ready`: 정확한 현재 ToolSpec fingerprint에 invoker가 바인딩됨
- `intentionally_unbound`: 신뢰된 로컬 설정에서 실행을 명시적으로 비활성화함
- `missing_trusted_config`: 저장된 contract는 유효하지만 필요한 live authority가 제공되지 않음
- `incompatible`: 제공된 live object, transport fingerprint 또는 concurrent contract가 저장된 capability와 일치하지 않음
- `failed`: 그 밖의 이유로 trusted binding 생성 실패

필수 capability가 `ready`가 아닐 때 시작 자체를 실패시키려면 `strict=True`를 사용합니다. `required_tools`를 생략하면 strict mode는 저장된 모든 capability를 필수로 취급합니다.

strict 실패는 `BindingReconciliationError`(`RegistrationError`의 subclass)를 발생시킵니다. `.report`에는 credential이 포함되지 않은 동일한 reconciliation report가 유지되므로, 시작 로그나 운영 진단을 위해 trusted resolver 설정을 재구성하거나 노출할 필요가 없습니다.

## 보안 경계

재바인딩은 ToolSpec을 다시 수집하거나 교체하지 **않습니다**. binding 직전에 registry fingerprint를 읽어 executor에 예상 contract fingerprint로 전달합니다. invoker 저장 전에 다른 writer가 contract를 바꾸면 binding은 fail-closed로 실패합니다.

저장된 실행 URL은 이미 승인된 실행 위치를 나타내는 경우에만 재사용됩니다. 명시적 승인이 필요했던 schema-document 제안은 애플리케이션이 trusted base URL을 제공할 때까지 unbound 상태로 남습니다.

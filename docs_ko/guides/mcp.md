# MCP

SchemaRouter는 공식 MCP Python SDK를 사용하되 **MCP protocol과 transport를 분리**합니다.
Streamable HTTP, local stdio subprocess, caller-owned transport-neutral client factory를
지원합니다.

## 설치

```bash
pip install "schemarouter[mcp]"
```

저장소 개발:

```bash
pip install -e ".[dev,mcp]"
```

## Streamable HTTP import

```python
from schemarouter import ExecutionPolicy, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
    policy=ExecutionPolicy(
        allow_unclassified_remote=True,
    ),
)
```

Discovery는 protocol negotiation, `list_tools()` pagination, `inputSchema` /
`outputSchema` import를 수행합니다.

## Local stdio server

```python
import os
import sys

tool = await router.add_mcp_stdio(
    sys.executable,
    args=["/opt/my_server.py"],
    env={"API_TOKEN": os.environ["API_TOKEN"]},
    allowed_commands=[sys.executable],
    provider="my-provider",
)
```

`command`, `args`, `cwd`, `env`는 trusted local configuration입니다. Model-selectable
argument가 아니며 canonical `ToolSpec`에 secret 값을 복사하지 않습니다.

SchemaRouter는 `shell=True`를 사용하지 않으며 shell command string을 받지 않습니다.

## Caller-owned client factory

이미 transport lifecycle을 애플리케이션이 소유한다면 fake URL을 만들 필요가 없습니다.

```python
tool = await router.add_mcp_client_factory(
    my_bound_factory,
    name="enterprise-mcp",
    transport="enterprise-tunnel",
    transport_fingerprint="corp-mcp-v3",
)
```

Factory는 credential과 transport state를 소유하고 SchemaRouter는 연결된 MCP client의
`list_tools()` / `call_tool()`만 사용합니다.

## 인증된 HTTP

```python
import os

router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    trusted_headers={
        "Authorization": f"Bearer {os.environ['MCP_TOKEN']}",
    },
)
```

Credential은 planner state, `ToolSpec`, model-visible argument로 복사되지 않습니다.
복잡한 OAuth, mTLS, proxy, gateway는 `MCPClientFactory`로 caller가 lifecycle을 소유하는
방식이 권장됩니다.

## Schema refresh / watch

```python
router.register_schema_watch(tool.key, interval_seconds=300)
await router.start_schema_watcher()
```

Identical schema는 no-op입니다. Compatible drift는 compare-and-swap 경계에서 처리할 수 있고,
breaking/security-semantic drift는 pending review 상태로 남습니다.

Process-local trusted binding이 없거나 stale하면 refresh는 fail-closed입니다.

## MCP annotation은 permission이 아닙니다

Remote server가 보내는 annotation은 descriptive metadata입니다. 로컬 execution authority가
아닙니다.

기본적으로 remote MCP operation은 side effect가 unclassified이므로 실행이 보수적으로 제한됩니다.

```python
ExecutionPolicy(allow_unclassified_remote=True)
```

필요하면 approval을 추가합니다.

```python
ExecutionPolicy(
    allow_unclassified_remote=True,
    approval_mode="non_read_only",
)
```

## 서버가 공개하지 않는 result contract 선언

MCP의 `outputSchema`는 optional입니다. 서버가 전체 결과를 text block으로만 반환하면
SchemaRouter가 output field를 안전하게 추론할 근거가 없습니다.

Trusted local code는 명시적으로 contract를 보완할 수 있습니다.

```python
from schemarouter import FieldSpec

tool = router.registry.get(key)
endpoint = tool.endpoint("lookup")

amended_endpoint = endpoint.model_copy(
    update={
        "output_fields": [
            FieldSpec(
                name="band_gap",
                semantic_id="materials.band_gap",
                unit="eV",
                qualifiers={"method": "measured"},
            ),
        ]
    }
)

amended = tool.model_copy(
    update={
        "endpoints": [
            amended_endpoint if candidate.name == endpoint.name else candidate
            for candidate in tool.endpoints
        ]
    }
)

router.amend_capability(key, amended)
```

이 기능은 단순 주석이 아닙니다. semantic ID, unit, path, evidence metadata는 routing,
projection, normalization, fallback eligibility에 영향을 줄 수 있으므로 trusted local declaration로만
허용됩니다.

이미 remote server가 선언한 execution identity나 validation shape를 임의로 바꾸면
`ContractAmendmentError`가 발생합니다.

## CI coverage

Repository CI는 실제 Streamable HTTP와 stdio MCP server를 올려 discovery → schema import →
planning → execution policy → `call_tool()` → structured output validation을 검증합니다.

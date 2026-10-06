# MCP

SchemaRouter는 공식 MCP Python SDK를 사용합니다. MCP 자체의 tool contract와 연결 방식을
분리해 두었기 때문에 Streamable HTTP, 로컬 stdio subprocess, 애플리케이션이 직접 관리하는
client factory를 같은 경계에서 사용할 수 있습니다.

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

연결되면 protocol negotiation을 수행하고 `list_tools()`를 끝까지 조회한 뒤,
각 tool의 `inputSchema`와 `outputSchema`를 등록합니다.

### Discovery 리소스 제한

MCP의 원격 tool catalog는 신뢰하지 않는 입력으로 취급합니다. 기본 한도는 한 번의 inspection
기준 64 pages, 512 tools, tool descriptor 하나당 512 KiB, 전체 catalog 4 MiB입니다. 기존
`timeout`은 page마다 새로 적용되는 시간이 아니라 전체 discovery walk의 상한입니다.
같은 cursor의 반복이나 cursor cycle도 거부합니다.

애플리케이션이 필요에 따라 한도를 더 낮추거나 명시적으로 높일 수 있습니다.

```python
from schemarouter import MCPDiscoveryLimits

limits = MCPDiscoveryLimits(
    max_pages=16,
    max_tools=200,
    max_tool_bytes=256 * 1024,
    max_total_bytes=2 * 1024 * 1024,
)

router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    mcp_discovery_limits=limits,
    timeout=15.0,
)
```

같은 `MCPDiscoveryLimits`를 `add_url()`, `probe_url()`, `add_mcp_stdio()`,
`add_mcp_client_factory()`, `arefresh_schema()`에도 사용할 수 있습니다. 한도를 넘기면
부분 catalog를 등록하지 않고 `SchemaSourceError`로 실패합니다.

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

`command`, `args`, `cwd`, `env`는 애플리케이션이 관리하는 로컬 설정입니다. 모델이
선택할 수 있는 인자가 아니며, 환경 변수의 secret 값도 `ToolSpec`에 복사하지 않습니다.

Subprocess 실행에는 `shell=True`를 쓰지 않고 shell command 문자열도 받지 않습니다.

## Caller-owned client factory

애플리케이션이 이미 MCP 연결의 수명주기를 관리하고 있다면 억지로 HTTP URL을 만들 필요가
없습니다.

```python
tool = await router.add_mcp_client_factory(
    my_bound_factory,
    name="enterprise-mcp",
    transport="enterprise-tunnel",
    transport_fingerprint="corp-mcp-v3",
)
```

Credential과 연결 상태는 factory 쪽에 남습니다. SchemaRouter는 넘겨받은 MCP client로
`list_tools()`와 `call_tool()`만 호출합니다.

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

Tool 목록이 그대로면 아무것도 바꾸지 않습니다. 호환 가능한 변경은 기존 fingerprint를 확인한
뒤 교체할 수 있고, breaking change나 보안 의미가 달라지는 변경은 검토 대기 상태로 남깁니다.

현재 process에 맞는 binding이 없거나 fingerprint가 오래됐으면 refresh를 진행하지 않습니다.

## MCP annotation은 permission이 아닙니다

Remote server가 보내는 annotation은 설명 정보일 뿐 로컬 실행 권한이 아닙니다.

따라서 side effect가 확실히 분류되지 않은 MCP operation은 기본 설정에서 실행하지 않습니다.

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

MCP에서 `outputSchema`는 필수가 아닙니다. 서버가 결과를 text block으로만 돌려주면
SchemaRouter가 field 구조를 안전하게 알아낼 근거가 없습니다.

이 경우 애플리케이션 코드에서 필요한 결과 계약을 직접 선언할 수 있습니다.

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

이 선언은 routing, projection, unit normalization, fallback 가능 여부에 실제로 영향을 줍니다.
그래서 원격 서버가 보내는 값이 아니라 애플리케이션이 신뢰하는 코드에서만 추가할 수 있습니다.

서버가 이미 선언한 실행 경로나 validation shape를 바꾸려 하면
`ContractAmendmentError`가 발생합니다.

## CI coverage

Repository CI는 실제 Streamable HTTP와 stdio MCP server를 올려 discovery → schema import →
planning → execution policy → `call_tool()` → structured output validation을 검증합니다.

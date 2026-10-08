# MCP

SchemaRouter는 공식 MCP Python SDK를 사용합니다. MCP 자체의 tool contract와 연결 방식을
분리해 두었기 때문에 Streamable HTTP, 로컬 stdio subprocess, 애플리케이션이 직접 관리하는
client factory를 같은 경계에서 사용할 수 있습니다.

## MCP SDK와 host-side selection의 경계

MCP Python SDK는 transport negotiation, `list_tools()`, `call_tool()` 같은 protocol/session
기능을 담당합니다. 발견된 tool 중 무엇을 agent에 노출할지, 큰 catalog에서 어떤 bounded
subset을 검색·선택할지는 SDK가 아니라 host 애플리케이션의 정책입니다.

SchemaRouter는 이 책임을 다음처럼 분리합니다.

```text
MCP server
  -> MCP Python SDK: protocol / transport / tools/list
  -> SchemaRouter: typed catalog ingestion
  -> host application: bounded retrieval / selection policy
  -> MCP Python SDK: 승인된 선택 tool의 call_tool()
```

이 경계는 MCP Python SDK maintainer도
[modelcontextprotocol/python-sdk#3617](https://github.com/modelcontextprotocol/python-sdk/issues/3617)에서
확인했습니다. 따라서 SchemaRouter의 bounded tool retrieval benchmark는 이 저장소에서
host-side 평가로 관리하며, MCP SDK에 selection policy hook이나 patch를 추가하지 않습니다.


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

연결되면 protocol negotiation을 수행하고 `list_tools()`를 조회한 뒤,
각 tool의 `inputSchema`와 `outputSchema`를 등록합니다.

### Discovery 리소스 제한

MCP catalog는 신뢰할 수 없는 입력으로 취급합니다. 반복/순환 cursor는 즉시 거부하며,
전체 discovery wall-clock timeout과 함께 page 수, tool 수, schema byte, 그리고 description과
annotation을 포함한 **전체 tool payload byte**를 제한합니다. 따라서 schema 자체가 작더라도
거대한 metadata를 보내 메모리 예산을 우회할 수 없습니다.

```python
from schemarouter import MCPDiscoveryLimits

limits = MCPDiscoveryLimits(
    max_pages=32,
    max_tools=512,
    max_tool_schema_bytes=256 * 1024,
    max_total_schema_bytes=4 * 1024 * 1024,
    max_tool_payload_bytes=512 * 1024,
    max_total_payload_bytes=8 * 1024 * 1024,
)

tool = await router.add_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    mcp_discovery_limits=limits,
)
```

기본값은 64 pages, 1,024 tools, tool schema당 512 KiB, 전체 schema 5 MiB,
tool payload당 1 MiB, 전체 payload 10 MiB입니다. 제한을 넘긴 discovery는
부분 catalog나 runtime binding을 등록하지 않고 실패합니다. 같은 limits는
`SchemaRouter.from_url()`, `probe_url()`, `add_mcp_client_factory()`, `add_mcp_stdio()`,
schema refresh에도 전달할 수 있습니다.

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

## Transport-neutral client factory

bound factory는 다음 형태를 가집니다.

```python
@asynccontextmanager
async def my_bound_factory(*, timeout: float = 20.0):
    async with my_mcp_client() as client:
        yield client
```

factory가 credential과 transport state를 소유하며 SchemaRouter는 연결된 MCP client만 `list_tools()`와 `call_tool()`에 사용합니다.

## 인증된 Streamable HTTP

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
동일한 trusted header set을 discovery와 runtime call에 사용하지만 header value는 `ToolSpec`, endpoint metadata, planner state, model-visible argument에 복사되지 않습니다. `Mcp-Protocol-Version` 같은 MCP protocol header는 trusted header로 override할 수 없으며 URL에 credential을 넣는 것도 거부합니다.

## Custom OAuth, mTLS, proxy 또는 gateway transport

더 복잡한 인증에는 `MCPClientFactory`를 주입합니다.

```python
router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    mcp_client_factory=my_trusted_factory,
)
```

factory가 공식 SDK client/transport lifecycle을 소유하므로 OAuth, client credential, mTLS, proxy, enterprise gateway 또는 application-specific HTTP client를 설정하면서 secret을 SchemaRouter planning contract 밖에 유지할 수 있습니다.

## Schema refresh / watch

```python
router.register_schema_watch(tool.key, interval_seconds=300)
await router.start_schema_watcher()
```

Tool 목록이 그대로면 아무것도 바꾸지 않습니다. 호환 가능한 변경은 기존 fingerprint를 확인한
뒤 교체할 수 있고, breaking change나 보안 의미가 달라지는 변경은 검토 대기 상태로 남깁니다.

live factory, credential, environment value, subprocess configuration, socket 등 transport state는 `ToolSpec`이나 watcher snapshot에 저장하지 않습니다. 현재 process-local binding이 없거나 stale이면 refresh는 fail closed하며 SchemaRouter가 HTTP URL이나 trusted transport state를 임의로 재구성하지 않습니다.

## 실행

bound invoker는 `call_tool()`을 호출합니다. structured content를 우선 사용하며 advertised output schema가 있으면 projection 전에 검증할 수 있습니다.

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

MCP에서 `outputSchema`는 필수가 아닙니다. 서버가 전체 결과를 text block으로 직렬화하면 SchemaRouter는 declared `outputSchema`에서만 output field를 도출하므로 projection/normalization할 field가 없습니다.

선언된 output array도 published `outputSchema`에서만 순회합니다. `results: array<object{title,url}>` 형태는 `results[].title`, `results[].url`을 노출하며 내부 `"*"` path segment가 projection 중 record alignment를 보존합니다. example tool response에서 array-item field를 추론하지 않습니다.

이 경우 애플리케이션 코드에서 필요한 결과 계약을 직접 선언할 수 있습니다.


## Integration coverage

```text
HTTP or stdio server
 -> discovery
 -> input/output schema import
 -> planning
 -> execution policy
 -> call_tool()
 -> structured output validation
```
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

# endpoint set은 고정됩니다. 선언할 endpoint 하나를 amend하면서
# 나머지 endpoint는 그대로 유지해야 합니다.
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

capability는 계속 executable하며 invoker는 사용자 코드에 노출되지 않습니다. 서버가 공개하지 않은 field를 선언하거나 기존 field의 의미를 annotate할 수 있지만 execution identity(path, method, parameter, read-only/destructive classification)나 서버가 공개한 field의 validation shape는 바꿀 수 없습니다. 그 외 변경은 `ContractAmendmentError`를 발생시키고 아무것도 변경하지 않습니다.

**이것은 inert annotation이 아닙니다.** 승인된 amendment는 실제 routing/result 경계를 바꿀 수 있습니다.

- semantic ID/unit 선언은 이전에 불가능했던 cross-provider fallback을 compatible하게 만들 수 있습니다.
- `unit_normalization`은 caller가 보기 전에 result path의 numeric value를 `item * scale + offset`으로 변환합니다.
- `path` / `result_path` 변경은 sanctioned field name이 반환하는 값을 바꿀 수 있으므로 projection/redaction boundary에 영향을 줍니다.
- `source_type`, `license`, `unit`은 executor가 hard gate로 강제하는 evidence availability에 영향을 줍니다.
- amendment는 tool fingerprint를 바꾸므로 해당 capability의 active availability cooldown을 초기화합니다.
- amendment 이전에 만든 LangChain/LlamaIndex bridge는 기존 fingerprint/output field를 캡처하므로 이후 호출에서 `SchemaDriftError`가 발생합니다. amended router에서 bridge tool을 다시 만들어야 합니다. `to_langgraph_node`는 매 호출마다 `router.invoke()`를 사용하므로 이 문제의 영향을 받지 않습니다.


Repository CI는 실제 Streamable HTTP와 stdio MCP server를 올려 discovery → schema import →
planning → execution policy → `call_tool()` → structured output validation을 검증합니다.

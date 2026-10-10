# MCP

SchemaRouter는 공식 MCP Python SDK를 사용합니다. MCP 자체의 tool contract와 연결 방식을
분리해 두었기 때문에 Streamable HTTP, 로컬 stdio subprocess, 애플리케이션이 직접 관리하는
client factory를 같은 경계에서 사용할 수 있습니다.

## MCP SDK와 host-side selection의 경계

MCP Python SDK는 transport negotiation, `list_tools()`, `call_tool()` 같은 protocol/session
기능을 담당합니다. 발견된 tool 중 무엇을 agent에 노출할지, 큰 catalog에서 어떤 bounded
subset을 검색·선택할지는 SDK가 아니라 host 애플리케이션의 정책입니다.

SchemaRouter는 이 책임을 다음처럼 분리합니다.

이 경계는 MCP Python SDK maintainer도
[modelcontextprotocol/python-sdk#3617](https://github.com/modelcontextprotocol/python-sdk/issues/3617)에서
확인했습니다. 따라서 SchemaRouter의 bounded tool retrieval benchmark는 이 저장소에서
host-side 평가로 관리하며, MCP SDK에 selection policy hook이나 patch를 추가하지 않습니다.

```text
MCP server
  -> MCP Python SDK: protocol / transport / tools/list
  -> SchemaRouter: typed catalog ingestion
  -> host application: bounded retrieval / selection policy
  -> MCP Python SDK: call_tool() for an authorized selected tool
```

## 설치

저장소 개발:

```bash
pip install "schemarouter[mcp]"
```

```bash
pip install -e ".[dev,mcp]"
```

## Streamable HTTP import

연결되면 protocol negotiation을 수행하고 `list_tools()`를 조회한 뒤,
각 tool의 `inputSchema`와 `outputSchema`를 등록합니다.

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

### Discovery 리소스 제한

MCP catalog는 신뢰할 수 없는 입력으로 취급합니다. 반복/순환 cursor는 즉시 거부하며,
전체 discovery wall-clock timeout과 함께 page 수, tool 수, schema byte, 그리고 description과
annotation을 포함한 **전체 tool payload byte**를 제한합니다. 따라서 schema 자체가 작더라도
거대한 metadata를 보내 메모리 예산을 우회할 수 없습니다.

기본값은 64 pages, 1,024 tools, tool schema당 512 KiB, 전체 schema 5 MiB,
tool payload당 1 MiB, 전체 payload 10 MiB입니다. 제한을 넘긴 discovery는
부분 catalog나 runtime binding을 등록하지 않고 실패합니다. 같은 limits는
`SchemaRouter.from_url()`, `probe_url()`, `add_mcp_client_factory()`, `add_mcp_stdio()`,
schema refresh에도 전달할 수 있습니다.

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

## Local stdio server

`command`, `args`, `cwd`, `env`는 애플리케이션이 관리하는 로컬 설정입니다. 모델이
선택할 수 있는 인자가 아니며, 환경 변수의 secret 값도 `ToolSpec`에 복사하지 않습니다.

Subprocess는 MCP SDK의 `StdioServerParameters`를 통해 실행합니다. `shell=True`를 사용하지 않으며 shell command 문자열도 받지 않습니다. `allowed_commands`는 실행 파일에 대한 선택적 명시 allowlist입니다. 환경 값에는 secret이 있을 수 있으므로 비밀이 아닌 환경 변수 **이름**만 transport fingerprint에 반영합니다. 가져온 MCP 도구는 로컬 subprocess라 해도 실행 정책상 원격·비신뢰 도구로 분류합니다. 로컬 subprocess 또한 임의의 부작용을 일으킬 수 있으므로 분류되지 않은 작업은 신뢰할 수 있는 로컬 정책에서 허용하지 않는 한 실행을 거부합니다.

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

## Caller-owned client factory

애플리케이션이 이미 MCP 연결의 수명주기를 관리하고 있다면 억지로 HTTP URL을 만들 필요가
없습니다.

Credential과 연결 상태는 factory 쪽에 남습니다. SchemaRouter는 넘겨받은 MCP client로
`list_tools()`와 `call_tool()`만 호출합니다.

호출자가 클라이언트 팩토리를 소유하면 SDK 전송 수명주기와 비밀 정보 처리를 애플리케이션 경계에서 통제할 수 있습니다. 클라이언트 바인딩을 보장하지 못한 경우에는 도구를 임의로 실행 가능한 상태로 추측하지 않습니다.

```python
tool = await router.add_mcp_client_factory(
    my_bound_factory,
    name="enterprise-mcp",
    transport="enterprise-tunnel",
    transport_fingerprint="corp-mcp-v3",
)
```

```python
@asynccontextmanager
async def my_bound_factory(*, timeout: float = 20.0):
    async with my_mcp_client() as client:
        yield client
```

## 인증된 HTTP

Credential은 planner state, `ToolSpec`, model-visible argument로 복사되지 않습니다.
복잡한 OAuth, mTLS, proxy, gateway는 `MCPClientFactory`로 caller가 lifecycle을 소유하는
방식이 권장됩니다.

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

같은 `trusted_headers`를 discovery와 runtime 호출에 적용하지만 헤더 **값**은 `ToolSpec`, endpoint metadata, planner state 또는 model-visible argument에 복사하지 않습니다. 특히 `Mcp-Protocol-Version` 같은 MCP 프로토콜 헤더는 `trusted_headers`로 재정의할 수 없고 URL 자체에 넣은 자격 증명도 거부합니다.

## 사용자 정의 OAuth, mTLS, 프록시 및 게이트웨이 전송 방식

OAuth, mTLS, 프록시, 기업용 게이트웨이 등 복잡한 인증이 필요하다면 신뢰할 수 있는 `MCPClientFactory`를 주입하십시오. 팩토리는 공식 MCP SDK 클라이언트와 전송 수명주기를 소유합니다. 이 경로를 통해 클라이언트 자격 증명, OAuth, mTLS, 전용 HTTP 클라이언트를 구성하되 비밀 정보는 SchemaRouter의 모델 노출 계획 계약 밖에 유지합니다. 이는 Streamable HTTP 전송에 전달하는 호출자 소유 HTTP 클라이언트에서 인증을 처리하는 MCP SDK의 계층 분리와 일치합니다.

```python
router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    mcp_client_factory=my_trusted_factory,
)
```

## Schema refresh / watch

Tool 목록이 그대로면 아무것도 바꾸지 않습니다. 호환 가능한 변경은 기존 fingerprint를 확인한
뒤 교체할 수 있고, breaking change나 보안 의미가 달라지는 변경은 검토 대기 상태로 남깁니다.

첫째, 모든 MCP transport는 동일한 보수적 schema drift 경계를 사용합니다. Streamable HTTP 등록은 저장된 안전한 URL provenance를 통해 다시 검사합니다. stdio 및 transport-neutral 등록에는 원래 URL이 없으므로 현재 프로세스에 바인딩된 fingerprint 일치 factory만 재사용합니다.

둘째, tool 목록이 같으면 no-op이고 호환 가능한 변경만 compare-and-swap 교체 경로를 통해 적용하여 새 fingerprint 아래 동일한 trusted transport factory에 다시 바인딩합니다. Breaking 또는 security-semantic drift는 review 대기 상태로 남으며 기존 승인된 계약이나 바인딩을 교체하지 않습니다.

셋째, live factory, credentials, env 값, subprocess 구성, socket 등 전송 상태는 `ToolSpec`이나 watcher snapshot에 저장하지 않습니다. 현재 process에 맞는 binding이 없거나 fingerprint가 오래됐으면 refresh는 fail-closed합니다. 새 HTTP URL을 꾸며 내거나 model-visible metadata에서 trusted transport 상태를 재구성하지 않습니다.

```python
router.register_schema_watch(tool.key, interval_seconds=300)
await router.start_schema_watcher()
```

## Execution

바인딩된 invoker는 실제 도구 호출을 위해 `call_tool()`을 사용합니다. 구조화된 응답 콘텐츠가 우선되며, SchemaRouter는 필드를 투영하기 전에 서버가 선언한 출력 스키마에 대해 이를 검증할 수 있습니다.

## MCP annotation은 permission이 아닙니다

Remote server가 보내는 annotation은 설명 정보일 뿐 로컬 실행 권한이 아닙니다.

따라서 side effect가 확실히 분류되지 않은 MCP operation은 기본 설정에서 실행하지 않습니다.

필요하면 approval을 추가합니다.

원격 MCP annotation은 신뢰할 수 있는 권한 승인 정보가 아닙니다. 읽기/쓰기·파괴적 작업 분류 및 승인은 호출자가 소유한 로컬 정책으로 결정합니다.

```python
ExecutionPolicy(allow_unclassified_remote=True)
```

```python
ExecutionPolicy(
    allow_unclassified_remote=True,
    approval_mode="non_read_only",
)
```

## CI coverage

Repository CI는 공식 SDK로 실제 Streamable HTTP 및 stdio MCP 서버를 실행하여 discovery, 입력·출력 스키마 수집, 계획, 실행 정책, `call_tool()`, 구조화된 출력 검증을 확인합니다. 별도의 전송 테스트로 자격 증명 격리와 안전하지 않은 헤더 차단도 검증합니다.

```text
HTTP or stdio server
 -> discovery
 -> input/output schema import
 -> planning
 -> execution policy
 -> call_tool()
 -> structured output validation
```

## 서버가 공개하지 않는 result contract 선언 {#declare-a-result-contract-the-server-does-not-publish}

MCP에서 `outputSchema`는 필수가 아닙니다. 서버가 결과를 text block으로만 돌려주면
SchemaRouter가 field 구조를 안전하게 알아낼 근거가 없습니다.

SchemaRouter는 공개된 `outputSchema`에서만 결과 필드를 도출합니다. 결과가 text block으로만 제공된다면 자동 projection/normalization 대상으로 삼을 필드가 없습니다. 공개 스키마에 `results: array<object{title,url}>`가 있을 경우에는 `results[].title`, `results[].url`처럼 배열 요소 필드를 도출하며, 내부 `"*"` 경로 세그먼트로 배열 항목의 정렬 관계를 보존합니다. 예시 응답의 형태를 보고 배열 요소 필드를 추론하지는 않습니다.

이 경우 애플리케이션 코드에서 필요한 결과 계약을 직접 선언할 수 있습니다.

이 선언은 routing, projection, unit normalization, fallback 가능 여부에 실제로 영향을 줍니다.
그래서 원격 서버가 보내는 값이 아니라 애플리케이션이 신뢰하는 코드에서만 추가할 수 있습니다.

서버가 이미 선언한 실행 경로나 validation shape를 바꾸려 하면
`ContractAmendmentError`가 발생합니다.

원격 서버가 `outputSchema`를 제공하지 않아도 애플리케이션이 신뢰하는 코드에서 결과 필드의 의미·단위·qualifier를 선언할 수 있습니다. 이 변경은 필드 선택·투영·단위 정규화·대체 경로·가용성 판단에 영향을 주므로 실제 원천이 보장하지 않는 정보를 근거 없이 선언해서는 안 됩니다.

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

# The endpoint set is frozen: amend the one endpoint you're declaring for and
# keep every other endpoint on the tool as-is, or amend_capability refuses
# with "endpoints removed" for any tool with more than one endpoint — which is
# the normal case for an imported MCP server.
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

승인된 변경은 capability의 실행 가능 상태를 유지하며 invoker 구현은 사용자 코드에 노출하지 않습니다. 미공개 필드를 선언하거나 기존 필드의 의미를 설명할 수 있지만, 실행 식별성(path, method, parameter, 읽기 전용 또는 파괴적 작업 분류)과 서버가 이미 공개한 필드의 validation shape는 변경할 수 없습니다. 이 밖의 변경은 `ContractAmendmentError`로 거부되며 원래 상태를 보존합니다.

**이것은 단순 설명용 주석이 아닙니다.** 승인된 수정은 다음 실제 실행 동작에 영향을 줍니다.

- **라우팅:** `semantic_id`나 단위 추가로 기존에 불가능했던 제공자 간 fallback이 호환 가능해질 수 있습니다.
- **값:** `unit_normalization`은 호출자에게 결과를 전달하기 전에 `item * scale + offset`으로 수치를 조정합니다.
- **투영 경계:** 기존 필드의 `path`나 `result_path` 수정은 같은 필드 이름으로 반환하는 데이터 위치를 바꿉니다. 이것은 field-selection의 redaction 경계이므로 기존에 제외됐던 내부 값을 노출시킬 위험이 있습니다. 예를 들어 `{"public": {"band_gap": 1.1}}` 대신 `{"internal": {"unreleased_band_gap": 9.9}}`를 가리키게 만들 수도 있습니다.
- **근거 게이트:** `source_type`, `license`, `unit`은 실행기가 강제하는 evidence availability를 바꾸므로 실제 서버 반환값은 그대로여도 선언만으로 차단됐던 경로를 통과시킬 수 있습니다.
- **접근 가용성:** `mark_access_unavailable`에 따른 cooldown은 tool fingerprint에 연결됩니다. 수정으로 fingerprint가 바뀌면 활성 cooldown이 해제됩니다. `add_tool(..., replace=True)`도 cooldown을 해제하지만 재바인딩 전까지 실행할 수 없고, amendment는 재발급된 바인딩 아래 실행 가능 상태를 유지한다는 차이가 있습니다.
- **프레임워크 브리지:** `to_langchain_tool`, `to_langchain_tools` 및 LlamaIndex 브리지는 생성 시 fingerprint와 output field 목록을 캡처합니다. 수정 이전 브리지는 이후 호출에서 모두 `SchemaDriftError`로 거부되므로 변경된 라우터로 다시 만들어야 합니다. 반면 `to_langgraph_node`는 매 호출 `router.invoke()`를 실행하므로 영향받지 않습니다.

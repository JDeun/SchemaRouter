# LangChain

SchemaRouter는 LangChain runtime을 대체하는 것이 아니라 optional boundary로 LangChain과 통합됩니다.

## 설치

사용자 설치:

```bash
pip install "schemarouter[langchain]"
```

저장소 개발 환경:

```bash
pip install -e ".[dev,langchain]"
```

Core package는 LangChain에 의존하지 않습니다.

## 기존 LangChain tool 가져오기

기존 LangChain `BaseTool` / `StructuredTool` object는 SchemaRouter의 canonical capability model로 compile하여 일반 execution pipeline에 bind할 수 있습니다:

```python
from langchain_community.tools import DuckDuckGoSearchRun
from schemarouter import SchemaRouter

router = SchemaRouter()
key = router.add_langchain_tool(
    DuckDuckGoSearchRun(),
    provider="duckduckgo",
    read_only=True,
    remote=True,
)
```

Importer는 tool의 declared input schema와, 존재하는 경우 declared output schema를 읽습니다.
Structured result lists keep their record shape: a declared `results: list[{title, url}]` can expose
`results[].title` and `results[].url` rather than collapsing the values into unrelated arrays.
Tool description에서 read/write authority를 추론하지 **않습니다**. `read_only`, `destructive`,
`remote`, `provider`, and `access_mode` remain trusted local classification.

This makes existing LangChain ecosystem tools usable as SchemaRouter capabilities without creating a
service-specific SchemaRouter adapter for every provider. Examples include web search, scholarly
search, finance, databases, and SaaS tools already represented as LangChain tools.

## 등록된 endpoint 내보내기

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

등록된 각 endpoint는 SchemaRouter input schema를 가진 LangChain `StructuredTool`이 됩니다.

To expose one endpoint:

```python
from schemarouter.integrations import to_langchain_tool

tool = to_langchain_tool(
    router,
    "weather",
    "current",
)
```

When `AuthorizationPolicy` is configured, pass the same trusted run configuration used by the
host application:

```python
from schemarouter import PrincipalContext, RunConfig

employee = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes={"department": "sales"},
)

tools = to_langchain_tools(
    router,
    run_config=RunConfig(principal=employee),
)
```

Only principal-visible endpoints are exported. DataScope field/parameter projection is applied
before LangChain receives the tool schema, and invocation returns through
`SchemaRouter.execute(..., config=...)` so trusted row/tenant filters and execution-time
authorization remain active.

## Live export contract

A `StructuredTool` captures the authorized endpoint schema visible at export time. Before every
invocation, SchemaRouter resolves the endpoint again and reapplies the current authorization and
DataScope view. If the endpoint schema, tool fingerprint, or authorized projected contract changed,
the call fails with `StaleExportedToolError` before execution.

Re-export the tool with `to_langchain_tool(...)` or rebuild the catalog with
`to_langchain_tools(...)` after schema refreshes or authorization-policy changes. This keeps a
framework agent from silently invoking a contract broader or different from the current live view.

## 실행 가능한 예제

The repository includes a minimal executable integration example:

```bash
python examples/langchain_quickstart.py
```

CI runs this example in addition to the dedicated integration tests, so the documented bridge is
kept executable.

## 실행은 계속 SchemaRouter를 통과

Integration은 원래 transport를 직접 호출하지 **않습니다**.

```text
LangChain StructuredTool
 -> SchemaRouter ToolCall
 -> current schema validation
 -> AuthorizationPolicy / DataScope
 -> ExecutionPolicy
 -> binding-drift check
 -> trusted invoker
 -> output validation
```

This means a LangChain agent gains the same fail-closed contracts as direct SchemaRouter usage.

## 책임 분리

권장 책임 분리는 다음과 같습니다.

| Concern | Owner |
| --- | --- |
| Agent graph / conversation | LangChain or LangGraph |
| Model invocation | Surrounding framework/application |
| Tool catalog schema | SchemaRouter |
| Endpoint/argument/field plan | SchemaRouter |
| Side-effect policy | SchemaRouter local policy |
| Tool execution validation | SchemaRouter |
| Checkpointing / memory | Surrounding framework |

SchemaRouter는 integration만을 위해 graph runtime을 중복 구현해서는 안 됩니다.

For direct `StateGraph` integration, see [LangGraph](langgraph.md).

## Packaging

The bridge currently stays in the main distribution behind the `langchain` extra. A separate
`langchain-schemarouter` package is deferred until an independent release cadence,
material dependency pressure, or an upstream ecosystem requirement justifies the split.

See [Compatibility testing](../compatibility.md) for the supported range and maintenance policy.

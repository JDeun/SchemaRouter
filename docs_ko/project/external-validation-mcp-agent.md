# mcp-agent 대규모 tool catalog 검증

Issue [#646](https://github.com/JDeun/SchemaRouter/issues/646)는 [mcp-agent](https://github.com/lastmile-ai/mcp-agent)가 MCP connection/session lifecycle과 workflow orchestration을 계속 소유하는 상태에서 SchemaRouter를 typed catalog-retrieval layer로 평가합니다.

Evidence surface는 공개된 `mcp-agent==0.2.6` package를 사용하며, 해당 release가 더 새로운 major MCP SDK로 조용히 이동하지 않도록 `mcp>=1.20,<2`를 명시적으로 고정합니다.

## 경계

```text
mcp-agent MCPApp
      |
      | owns stdio process + session
      v
mcp-agent Agent.list_tools()
      |
      | discovered Tool schemas
      v
non-executable SchemaRouter mirror
      |
query -> bounded allow-set
      |
      v
mcp-agent Agent.list_tools(tool_filter=...)
      |
      | shortlisted native MCP tools
      v
mcp-agent Agent.call_tool(...)
```

이 평가에서 SchemaRouter는 client session, MCP connection handle 또는 executable invoker를 받지 않습니다. 실제 tool call은 모두 `mcp-agent`를 통과합니다.

## Deterministic workflow

Local fixture는 weather, finance, travel, logistics, calendar, software, research, materials data에 걸친 mixed 12-tool catalog를 노출합니다.

Case는 다음을 포함합니다.

- single-capability weather request
- multi-capability hotel + restaurant request
- materials band-gap request
- research-paper request
- explicit no-route request

Supported case에서는 selected set을 mcp-agent native `Agent.list_tools(tool_filter=...)` surface에 전달합니다. Required shortlisted tool은 `Agent.call_tool(...)`을 통해 호출하므로 task completion은 SchemaRouter executor가 아니라 mcp-agent 자체 connection/session과 tool execution path를 사용합니다.

## Schema conversion contract

SchemaRouter mirror는 discovered MCP tool에 실제 존재하는 정보만 복사합니다.

- tool name과 description
- input JSON Schema
- 존재하는 경우 declared output JSON Schema
- MCP annotation이 명시적으로 제공하는 `readOnlyHint` / `destructiveHint`

Source가 선언하지 않은 output `FieldSpec`, unit, semantic ID, authorization rule 또는 execution binding은 추론하지 않습니다.

직접 대응되는 SchemaRouter typed slot이 없는 MCP annotation/top-level field는 opaque source metadata로 유지합니다. JSON artifact는 해당 key를 `typed_conversion_gaps` 아래 기록하여 schema friction을 숨기거나 만들어내지 않고 보이게 합니다.

## No-route behavior

Retrieval selector는 SchemaRouter ranking 이후 conservative identifier-overlap disclosure gate를 적용합니다. Positive raw lexical score만으로 capability가 지원된다고 간주하지 않습니다.

따라서 unsupported case는 empty mcp-agent filtered tool list를 생성해야 합니다.

## Evidence

Required package CI는 built SchemaRouter wheel을 fresh venv에 설치한 뒤 pinned mcp-agent evidence dependency를 설치하고 다음을 실행합니다.

```bash
python -m unittest \
  examples.external_validation.mcp_agent_catalog.contract_smoke -v

python scripts/external_validation_mcp_agent.py \
  --json-out artifacts/external-validation-mcp-agent.json
```

Uploaded artifact는 다음을 기록합니다.

- discovered tool count
- shortlist size
- required-tool recall
- unsupported rejection
- task completion
- routing latency
- mcp-agent를 통해 발생한 tool-call record
- schema preservation count
- typed conversion gap과 explicit authority-boundary flag

이는 [external adoption plan](external-adoption.md) 기준 **E0 maintainer-owned evidence**입니다. Independent validation이 아니며 SchemaRouter가 mcp-agent의 MCP runtime 또는 workflow orchestration을 대체한다고 주장하지 않습니다.

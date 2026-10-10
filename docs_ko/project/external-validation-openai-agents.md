# OpenAI Agents SDK 동적 MCP 필터 검증

Issue [#645](https://github.com/JDeun/SchemaRouter/issues/645)는 OpenAI Agents SDK의 기존 동적 MCP `tool_filter` 뒤에서 query-dependent allow-set을 만드는 역할로 SchemaRouter를 평가합니다.

근거 surface는 `openai-agents==0.22.3`에 고정합니다.

## 경계

```text
local stdio MCP server
        |
        | list_tools / input schemas
        v
retrieval-only SchemaRouter mirror
        |
query -> bounded tool-name allow-set
        |
        v
OpenAI Agents SDK dynamic tool_filter
        |
        v
Agents SDK FunctionTool conversion
approval / guardrails / eventual invocation
```

이 구성에서 SchemaRouter는 MCP connection lifecycle이나 tool execution을 소유하지 않습니다. Call을 승인하거나 MCP tool을 호출하거나 SDK의 input/output guardrail을 대체하지 않습니다.

Filter는 현재 run context에 노출되는 discovered MCP tool만 변경합니다. 이 visibility decision은 model-generated argument 또는 resource에 대한 authorization이 아닙니다.

## 실제 local MCP lifecycle

평가는 현재 Python interpreter를 사용해 `MCPServerStdio`로 `examples/external_validation/openai_agents_mcp_filter/server.py`를 실행합니다.

첫 번째 unfiltered connection이 mixed tool catalog와 input schema를 발견합니다. 이후 SchemaRouter가 retrieval-only mirror를 등록합니다. 두 번째 Agents SDK server connection은 `RunContextWrapper.context`에서 query를 얻는 dynamic `ToolFilterContext` callback을 사용합니다.

Hosted model이나 API key는 사용하지 않습니다.

## Approval 및 guardrail 보존

Filtered MCP server는 다음으로 구성됩니다.

- `require_approval="always"`
- SDK input tool guardrail 하나
- SDK output tool guardrail 하나

Filtering 이후 평가는 Agents SDK가 일반 MCP-backed `FunctionTool` object를 생성하게 하고, 노출된 모든 tool에 approval policy와 두 guardrail list가 그대로 있는지 확인합니다.

Supported case 하나는 destructive-style `delete_record` capability를 의도적으로 선택합니다. 요청되면 visible일 수 있지만 filtering이 SDK approval 또는 guardrail boundary를 제거해서는 안 됩니다.

Local MCP server는 실제 tool-body invocation도 temporary call log에 기록합니다. Validation은 discovery/filter conversion만 수행하며 call log는 비어 있어야 합니다.

## No-route gate

PydanticAI 평가와 마찬가지로 raw positive SchemaRouter lexical score를 authorization 또는 abstention probability로 취급하지 않습니다. Filter는 bounded tool identifier relevance signal 또는 explicit preferred route가 있는 candidate만 노출합니다.

이를 통해 generic description overlap이 unsupported query를 non-empty MCP tool list로 바꾸는 것을 방지합니다.

## Evidence

Required CI는 SchemaRouter wheel을 build하고 clean virtual environment에 pinned Agents SDK와 함께 설치한 뒤 focused `unittest` contract를 실행하고 다음을 생성합니다.

```text
artifacts/external-validation-openai-agents.json
```

Artifact는 다음을 기록합니다.

- discovered/shortlisted tool count
- full/filtered serialized schema bytes
- required-tool recall
- unsupported-query rejection
- shortlist task success
- routing latency
- schema-fidelity count
- approval/guardrail preservation
- observed MCP tool-body call count

Serialized byte count는 token count가 아닙니다.

이는 [external adoption plan](external-adoption.md) 기준 **E0 maintainer-owned evidence**입니다. External adoption, independent reproduction 또는 final model-answer superiority를 보여주지 않습니다.

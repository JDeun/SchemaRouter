# OpenAI Agents SDK dynamic MCP filter validation

Issue [#645](https://github.com/JDeun/SchemaRouter/issues/645) evaluates SchemaRouter as the
query-dependent allow-set behind the OpenAI Agents SDK's existing dynamic MCP `tool_filter`.

The evidence surface is pinned to `openai-agents==0.22.3`.

## Boundary

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

SchemaRouter does **not** own MCP connection lifecycle or tool execution in this composition. It
does not approve calls, invoke MCP tools, or replace the SDK's input/output guardrails.

The filter changes only which discovered MCP tools are exposed for the current run context. That
visibility decision is not authorization for model-generated arguments or resources.

## Real local MCP lifecycle

The evaluation launches
`examples/external_validation/openai_agents_mcp_filter/server.py`
through `MCPServerStdio` using the current Python interpreter.

A first unfiltered connection discovers the mixed tool catalog and input schemas. SchemaRouter then
registers a retrieval-only mirror. A second Agents SDK server connection uses a dynamic
`ToolFilterContext` callback whose query comes from `RunContextWrapper.context`.

No hosted model or API key is used.

## Approval and guardrail preservation

The filtered MCP server is configured with:

- `require_approval="always"`;
- one SDK input tool guardrail;
- one SDK output tool guardrail.

After filtering, the evaluation asks the Agents SDK to produce its normal MCP-backed
`FunctionTool` objects and checks that every revealed tool still carries the approval policy and
both guardrail lists.

One supported case deliberately selects a destructive-style `delete_record` capability. It may be
visible when requested, but filtering must not strip the SDK approval or guardrail boundary.

The local MCP server also records every actual tool-body invocation to a temporary call log. The
validation performs discovery/filter conversion only and requires that call log to stay empty.

## No-route gate

As in the PydanticAI evaluation, raw positive SchemaRouter lexical score is not treated as an
authorization or abstention probability. The filter reveals only candidates with a bounded tool
identifier relevance signal (or an explicit preferred route).

This prevents generic description overlap from turning an unsupported query into a non-empty MCP
tool list.

## Evidence

Required CI builds the SchemaRouter wheel, installs it into a clean virtual environment with the
pinned Agents SDK, runs the focused `unittest` contract, then emits:

```text
artifacts/external-validation-openai-agents.json
```

The artifact records:

- discovered and shortlisted tool counts;
- full and filtered serialized schema bytes;
- required-tool recall;
- unsupported-query rejection;
- shortlist task success;
- routing latency;
- schema-fidelity counts;
- approval and guardrail preservation;
- observed MCP tool-body call count.

Serialized byte counts are not token counts.

This is **E0 maintainer-owned evidence** under the
[external adoption plan](external-adoption.md). It does not show external adoption, independent
reproduction, or final model-answer superiority.

# mcp-agent large-tool-catalog validation

Issue [#646](https://github.com/JDeun/SchemaRouter/issues/646) evaluates SchemaRouter as a typed
catalog-retrieval layer while [mcp-agent](https://github.com/lastmile-ai/mcp-agent) continues to own
MCP connection/session lifecycle and workflow orchestration.

The evidence surface uses the published `mcp-agent==0.2.6` package and explicitly pins
`mcp>=1.20,<2` so the evaluation does not silently move that release onto a newer major MCP SDK.

## Boundary

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

SchemaRouter never receives a client session, MCP connection handle, or executable invoker in this
evaluation. Every actual tool call goes through `mcp-agent`.

## Deterministic workflow

The local fixture exposes a mixed 12-tool catalog spanning weather, finance, travel, logistics,
calendar, software, research, and materials data.

The cases include:

- a single-capability weather request;
- a multi-capability hotel + restaurant request;
- a materials band-gap request;
- a research-paper request;
- an explicit no-route request.

For supported cases, the selected set is passed to mcp-agent's native
`Agent.list_tools(tool_filter=...)` surface. Required shortlisted tools are then invoked through
`Agent.call_tool(...)`, so task completion exercises mcp-agent's own connection/session and tool
execution path rather than a SchemaRouter executor.

## Schema conversion contract

The SchemaRouter mirror copies only information actually present in the discovered MCP tool:

- tool name and description;
- input JSON Schema;
- declared output JSON Schema when present;
- `readOnlyHint` / `destructiveHint` when the MCP annotations explicitly provide them.

No output `FieldSpec`, unit, semantic ID, authorization rule, or execution binding is inferred when
the source does not declare it.

MCP annotation/top-level fields without a direct SchemaRouter typed slot are retained as opaque
source metadata. The JSON artifact lists those keys under `typed_conversion_gaps` so schema
friction is visible rather than silently discarded or fabricated.

## No-route behavior

The retrieval selector applies a conservative identifier-overlap disclosure gate after SchemaRouter
ranking. Positive raw lexical score alone is not treated as proof that a capability is supported.

The unsupported case must therefore produce an empty mcp-agent filtered tool list.

## Evidence

Required package CI installs the built SchemaRouter wheel into a fresh venv, then installs the
pinned mcp-agent evidence dependencies and runs:

```bash
python -m unittest \
  examples.external_validation.mcp_agent_catalog.contract_smoke -v

python scripts/external_validation_mcp_agent.py \
  --json-out artifacts/external-validation-mcp-agent.json
```

The uploaded artifact records:

- discovered tool count;
- shortlist sizes;
- required-tool recall;
- unsupported rejection;
- task completion;
- routing latency;
- tool-call records made through mcp-agent;
- schema preservation counts;
- typed conversion gaps and explicit authority-boundary flags.

This is **E0 maintainer-owned evidence** under the
[external adoption plan](external-adoption.md). It is not independent validation and does not claim
that SchemaRouter replaces mcp-agent's MCP runtime or workflow orchestration.

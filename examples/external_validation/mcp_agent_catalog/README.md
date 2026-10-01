# mcp-agent large-tool-catalog validation

This maintainer-owned E0 evaluation composes SchemaRouter retrieval with
`mcp-agent`'s normal MCP application, connection/session, filtering, and tool-call
lifecycle.

SchemaRouter receives a non-executable mirror of the discovered tool schema surface
and returns only a bounded allow-set. `mcp-agent` remains the transport/session
owner and invokes every tool directly.

## Pinned evidence surface

```text
mcp-agent==0.2.6
mcp>=1.20,<2
```

The explicit MCP v1 bound keeps this evaluation on the protocol line used by the
published mcp-agent 0.2.6 package instead of silently testing that older release
against a newer major MCP SDK.

## Reproduce

Use a clean environment with an installed SchemaRouter wheel:

```bash
python -m venv .venv-mcp-agent-validation
. .venv-mcp-agent-validation/bin/activate
pip install /path/to/schemarouter-*.whl
pip install -r examples/external_validation/mcp_agent_catalog/requirements.txt

python -m unittest \
  examples.external_validation.mcp_agent_catalog.contract_smoke -v

python scripts/external_validation_mcp_agent.py \
  --json-out /tmp/mcp-agent-catalog.json
```

No hosted model or provider API key is used. A deterministic local stdio MCP server
is spawned by mcp-agent itself.

The JSON evidence records:

- discovered and shortlisted tool counts;
- required-tool recall;
- unsupported-query rejection;
- deterministic task completion through direct `mcp-agent` tool calls;
- routing latency;
- full versus shortlisted serialized schema bytes;
- exact input/output schema preservation where the source declares them;
- typed conversion gaps for MCP fields that have no direct SchemaRouter typed slot;
- explicit confirmation that no execution binding or authority metadata was fabricated.

Serialized bytes are not model-token counts. Task completion here measures the
deterministic filtered workflow, not final LLM answer quality.

Tracked by SchemaRouter issues #646 and #584.

# OpenAI Agents SDK dynamic MCP filter validation

This maintainer-owned E0 evaluation composes SchemaRouter retrieval with the
OpenAI Agents SDK's public dynamic MCP `tool_filter` surface.

SchemaRouter supplies only the query-dependent bounded allow-set. The Agents SDK
keeps the stdio MCP process/session lifecycle, MCP-to-FunctionTool conversion,
approval policy, input/output guardrails, and eventual invocation semantics.

## Reproduce

Use a clean environment with an installed SchemaRouter wheel:

```bash
python -m venv .venv-openai-agents-validation
. .venv-openai-agents-validation/bin/activate
pip install /path/to/schemarouter-*.whl
pip install -r examples/external_validation/openai_agents_mcp_filter/requirements.txt
python -m unittest \
  examples.external_validation.openai_agents_mcp_filter.contract_smoke -v
python scripts/external_validation_openai_agents.py \
  --json-out /tmp/openai-agents-mcp-filter.json
```

The evaluation launches a deterministic local stdio MCP server. It does not use a
hosted model, OpenAI API key, or remote provider.

The JSON evidence records:

- discovered MCP tool count;
- full and filtered serialized schema bytes;
- shortlist size;
- required-tool recall;
- unsupported-query rejection;
- retrieval-task success/failure;
- routing latency;
- MCP-to-SchemaRouter input-schema fidelity;
- approval and input/output guardrail preservation;
- whether any MCP tool body executed during the evaluation.

Serialized bytes are not model-token counts. Shortlist correctness is not
final-answer quality.

Tracked by SchemaRouter issues #645 and #584.

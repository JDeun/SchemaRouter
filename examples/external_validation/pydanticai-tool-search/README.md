# PydanticAI ToolSearch external validation

This maintainer-owned E0 evaluation composes SchemaRouter with PydanticAI's public
`ToolSearch(strategy=...)` API.

It does **not** replace PydanticAI's tool lifecycle or execution authority. The
SchemaRouter side contains a retrieval-only mirror of PydanticAI `ToolDefinition`
objects and returns only bounded tool names. PydanticAI remains responsible for
deferred-tool disclosure, lifecycle, validation, approvals, and execution.

## Reproduce

Use a clean environment with an installed SchemaRouter wheel:

```bash
python -m venv .venv-pydanticai-validation
. .venv-pydanticai-validation/bin/activate
pip install /path/to/schemarouter-*.whl
pip install -r examples/external_validation/pydanticai-tool-search/requirements.txt
python scripts/external_validation_pydanticai.py \
  --json-out /tmp/pydanticai-tool-search.json
```

No provider API key, remote model, or network service is required after installation.

The custom strategy includes an explicit no-route disclosure gate. Raw positive
SchemaRouter lexical score is treated as recall evidence, **not** as support: a tool is revealed only
when a typed field matches, it was explicitly preferred, or a matched token belongs to the registered
tool identifier itself. Per-case raw scores/components and the final gate signal are written to the
JSON output.

The script records:

- declared deferred-tool count;
- full versus revealed serialized schema bytes;
- required-tool recall;
- unsupported-query rejection;
- retrieval-task success/failure;
- added routing latency;
- exact input-schema mirror matches;
- explicit fidelity limits.

Serialized bytes are **not** reported as model tokens. Retrieval-task success is
**not** final-answer quality.

Tracked by SchemaRouter issues #644 and #584.

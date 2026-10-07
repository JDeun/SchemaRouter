# Discoverability and positioning

SchemaRouter should be discoverable without pretending to be a general agent framework, MCP server,
or model router.

## Canonical positioning

Use this sentence as the default long-form description:

> **SchemaRouter is a typed capability routing and governed execution layer for AI agents across
> APIs, tools, and data systems.**

Supporting variants may be shorter, but they must preserve the same product boundary.

### Short variant

> Typed capability routing and governed execution for AI agents.

### Ecosystem variant

> Put APIs, MCP tools, SDKs, and data systems behind one typed capability boundary instead of
> dumping the entire capability catalog into model context.

## What it is / is not

SchemaRouter **is**:

- a typed tool/capability registry;
- a capability-retrieval layer;
- a schema-aware planning and execution boundary;
- an MCP/OpenAPI/Python/tool-framework integration layer;
- a validation, projection, policy, health, and schema-lifecycle boundary.

SchemaRouter is **not**:

- a general agent framework;
- an LLM provider gateway;
- a model router;
- an MCP server catalog;
- a document retriever or final-answer generator.

This distinction matters for both technical accuracy and search quality. A visitor searching for
"tool routing" should not be led to believe that SchemaRouter routes between LLM models.

## Search vocabulary

Use these terms naturally where they describe real capabilities:

- agent tool routing;
- typed tool registry;
- capability retrieval;
- schema-aware execution;
- MCP tools;
- OpenAPI tools;
- JSON Schema validation;
- LangChain tools;
- LangGraph integration;
- LlamaIndex tools;
- RAG tool execution;
- provider/access fallback;
- field projection.

Do not repeat terms solely for ranking.

## Surface alignment

The project should keep the following aligned for every stable release:

| Surface | Requirement |
| --- | --- |
| GitHub description | one-sentence typed capability/execution positioning |
| GitHub homepage | published documentation site |
| GitHub topics | protocols/frameworks actually supported |
| README first screen | problem statement + canonical positioning + install |
| PyPI summary | same product category and boundary |
| PyPI keywords | real protocols/frameworks/search terms only |
| Docs home | current stable version and same product boundary |
| Release notes | stable product claims separated from research claims |

## Recommended GitHub topics

Current topics already cover most of the intended surface. When editing repository settings, retain
the accurate existing topics and add the missing high-signal terms when useful:

- `langgraph`;
- `capability-retrieval`;
- `schema-aware-execution`.

Do not add unrelated high-volume topics.

The repository homepage should remain the published docs URL. Social preview is handled by the
release checklist.

## External listing opportunities

Listing submissions are gated by the destination's own rules and by SchemaRouter's evidence.

| Destination | Fit | Current status |
| --- | --- | --- |
| `Christian-Sidak/awesome-mcp-tools` | MCP frameworks/tools | **Defer** until there is demonstrated external/community value; its rules reject shallow self-promotion. |
| `kaushikb11/awesome-llm-agents` | Agent Infrastructure | **Not yet eligible**: its current policy requires at least 25 stars unless published by a recognized organization/research lab. |
| `awesome-llms-labs/awesome-ai-agents` | Agent infrastructure/ecosystem | **Defer** until genuine external usage/influence is documented. |
| Model-routing awesome lists | Routes between LLM models | **Do not submit**; SchemaRouter is a tool/capability router, not a model router. |
| MCP server-only catalogs | MCP servers | **Do not submit**; SchemaRouter consumes/integrates MCP capability sources but is not itself an MCP server directory. |

LangChain/LlamaIndex distribution is tracked separately in issue #10 because upstream package/listing
policy can change independently of general discoverability work.

## Release discoverability checklist

Before a stable release:

- [ ] README, docs home, PyPI summary, and release notes name the same stable version.
- [ ] Canonical positioning still matches the actual product boundary.
- [ ] New protocol/framework names are added only after first-class support exists.
- [ ] Deprecated/removed integrations are removed from search metadata.
- [ ] PyPI keywords and project URLs still resolve to maintained surfaces.
- [ ] GitHub description, topics, homepage, and social preview are reviewed.
- [ ] Example gallery contains at least one runnable path for each advertised major integration.
- [ ] Benchmark/research claims link to reproducible evidence and remain separate from stable product
  claims.
- [ ] External listing eligibility is re-checked before submission; never assume an old contribution
  policy still applies.

## Submission rule

Do not submit SchemaRouter to an external directory merely to gain a backlink. Submit only when:

1. the category accurately describes the project;
2. the repository satisfies that directory's current objective requirements;
3. the linked quickstart/docs work;
4. the description avoids unsupported performance claims;
5. external usage/evidence is sufficient for lists that require community value.

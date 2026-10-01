# Discoverability and positioning

This page is the canonical metadata and search-surface checklist for SchemaRouter. It exists to keep
GitHub, PyPI, the documentation site, release notes, and ecosystem listings consistent without
turning project copy into keyword stuffing.

Status date: **2026-10-01**

## Canonical positioning

Use this sentence whenever a one-line product description is needed:

> **SchemaRouter is a typed capability retrieval and execution layer for RAG and LLM agents across
> OpenAPI, MCP, OPTIMADE, and Python tools.**

Supporting variants:

- **Short:** A typed boundary between agents and heterogeneous tools.
- **Search-oriented:** Retrieve a bounded set of typed tool capabilities and execute them through
  validated OpenAPI, MCP, OPTIMADE, Python, SDK, and framework integration surfaces.
- **Architecture-oriented:** The surrounding agent owns reasoning and orchestration; SchemaRouter
  owns capability contracts, bounded retrieval, validation, policy, and execution.

The project must not describe itself as a general agent framework, model-provider abstraction, or
standalone RAG generator.

## Search terminology

Use these terms only where they accurately describe a supported surface:

- agent tool routing
- typed tool registry
- capability retrieval
- schema-aware execution
- tool calling
- MCP tools
- OpenAPI tools
- OPTIMADE
- JSON Schema
- RAG / retrieval-augmented generation
- LangChain
- LangGraph
- LlamaIndex

Framework names belong in metadata because tested integration surfaces exist. Do not add the name of
a framework, provider, protocol, or benchmark merely because it is popular.

## Current metadata audit

| Surface | 2026-10-01 state | Action |
| --- | --- | --- |
| GitHub description | already uses the canonical positioning | keep |
| GitHub homepage | points to the published docs | keep |
| GitHub topics | strong base; missing some supported search terms | add the topics below in repository settings |
| README first screen | logo, problem statement, install command, stable release, canonical positioning | keep synchronized |
| PyPI description | aligned through pyproject.toml | verify after each release |
| PyPI keywords | expanded to protocol, retrieval, tool-calling, and tested framework terms | verify after each release |
| PyPI project URLs | docs/repository/issues/research/brand plus examples/changelog | verify after each release |
| MkDocs site description | aligned with the canonical positioning | keep synchronized |
| Social preview source | docs/assets/brand/schemarouter-social-preview.svg exists | repository Settings preview must be verified manually |

### GitHub topics

Topics currently visible through the repository metadata API:

- ai-agents
- json-schema
- langchain
- llamaindex
- llm
- mcp
- openapi
- optimade
- python
- rag
- retrieval-augmented-generation
- structured-data
- tool-routing

Add these supported terms when repository-settings access is available:

- langgraph
- tool-calling
- capability-retrieval

Do not remove the existing protocol and RAG topics merely to add synonyms.

## External listing opportunities

Submission is contribution-first: read each list's current rules, submit an accurate category and
description, and do not ask for votes or stars.

| Opportunity | Why it fits | Status |
| --- | --- | --- |
| https://github.com/abordage/awesome-mcp | includes MCP clients/frameworks and adjacent tooling | candidate; not submitted |
| https://github.com/Christian-Sidak/awesome-mcp-tools | explicitly covers SDKs, libraries, frameworks, and adapters | candidate; not submitted |
| https://github.com/awesome-llms-labs/awesome-ai-agents | broad agent ecosystem including supporting infrastructure | candidate; not submitted |
| PyPI | canonical Python package index | published; metadata maintained in pyproject.toml |
| LangChain / LlamaIndex upstream ecosystem paths | direct framework distribution is stronger than an awesome-list mention | tracked separately in issue #10 |

The official MCP client list is **not** an appropriate target merely because SchemaRouter supports
MCP: SchemaRouter is not itself an end-user MCP client. Prefer framework/tooling lists whose scope
matches the project.

External lists change their scope and contribution rules. Re-check them immediately before opening a
submission PR.

## First-screen test

A new visitor should be able to answer all four questions without scrolling through research detail:

1. **What problem is this solving?** Too many heterogeneous tool schemas and over-broad tool output.
2. **What is the product?** A typed capability retrieval and execution boundary.
3. **What can I connect?** OpenAPI, MCP, OPTIMADE, Python/SDK tools, plus documented protocol and
   framework integrations.
4. **What is it not?** It does not replace the agent framework, model provider, or final RAG
   generation layer.

## Release discoverability checklist

Before a release:

- compare the GitHub description with the canonical sentence above;
- verify the docs homepage URL;
- review GitHub topics against actual supported capabilities;
- confirm the social preview is still set from the approved brand source;
- inspect the built wheel metadata and PyPI rendering;
- verify PyPI keywords and project URLs;
- confirm the MkDocs site description and first-screen docs copy;
- confirm README and README.ko describe the same product boundary;
- check that examples named in metadata or launch copy still run in CI;
- revisit external-listing status and contribution rules;
- remove stale framework/provider names rather than preserving them for search traffic.

## Change policy

Discoverability work may improve wording, metadata, examples, and distribution. It must not silently
change the stable product boundary or turn unverified research results into product claims. If a new
term requires a new feature to be truthful, implement and validate the feature first.

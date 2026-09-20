# Changelog

All notable changes to SchemaRouter are documented here.

The project is pre-1.0 and follows the compatibility rules in
[`docs/versioning.md`](docs/versioning.md).

## Unreleased

No unreleased changes yet.

## 0.2.0a1 - 2026-09-20

### Added

- pluggable structured-source `AdapterRegistry` with explicit and priority-based auto discovery;
- OPTIMADE v1 discovery through base and entry-type info endpoints;
- OPTIMADE field-aware execution that maps planned fields to `response_fields`;
- call-aware invoker support for protocol adapters that need the full `ToolCall`;
- typed tool, endpoint, parameter, response-field, plan, and result contracts;
- namespaced versioned registry;
- schema-aware planning with recall-preserving field projection;
- provider-neutral model-assisted query analysis;
- OpenAPI 3.x URL ingestion and guarded HTTP execution;
- MCP tool discovery and execution;
- evidence-grounded proposals for human-readable API documentation;
- runtime JSON Schema validation for arguments and raw outputs;
- schema and invoker-binding drift detection;
- fail-closed execution policy for mutations, destructive calls, and unclassified remote tools;
- Runnable-style `invoke`, `batch`, `stream`, and typed event APIs;
- run configuration, concurrency control, and safe retry policy;
- typed Python callable registration with `@schema_tool`;
- optional LangChain `StructuredTool` integration;
- framework maturity, architecture, release, and versioning documentation;
- MIT licensing and package metadata;
- MkDocs Material documentation site with guides, recipes, and generated API reference;
- SchemaRouter brace-and-routing-hub brand system with light/dark marks, lockups, favicon, and social preview source artwork.

### Security

- separated schema-fetch credentials from runtime API credentials;
- restricted schema redirects and runtime API origins;
- blocked model/tool control of sensitive runtime headers;
- redacted event payloads by default;
- prevented automatic retries for non-read-only calls.

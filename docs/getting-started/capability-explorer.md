# Capability Explorer

SchemaRouter's Capability Explorer is a read-only, protocol-neutral contract browser for the
registered capability catalog. It provides the same kind of drill-down documentation experience
that Swagger UI provides for HTTP APIs, without assuming every capability is REST/OpenAPI.

The explorer supports OpenAPI, MCP, GraphQL, OData, OpenRPC, OPTIMADE, Python tools,
LangChain/LlamaIndex bridges, declarative HTTP, and custom/SDK-bound capabilities.

## Export a static explorer

```bash
schemarouter explorer \
  --registry ./schemarouter-registry.sqlite3 \
  --output ./schema-explorer.html
```

The generated file is self-contained. It has no CDN, remote script, stylesheet, or external asset
dependency, so it can be opened locally or attached to an internal artifact system.

## What it shows

Each tool is grouped into expandable endpoint contracts.

Tool-level information includes:

- key, name, provider, adapter, access mode and source type;
- safe source provenance;
- license and schema fingerprint;
- live binding/watch status when a live `RouterInspection` is supplied through Python.

Endpoint-level information includes:

- route ID, method/path or protocol identity;
- read-only, mutating, destructive or unclassified mode;
- trusted operation aliases;
- secret-free authentication requirements;
- logical/wire parameter names, locations and required state;
- serialization style/explode/allowReserved semantics;
- input and output JSON Schema;
- output field semantic IDs, aliases, source/result paths and identifier status;
- source units and explicit normalization dimension/canonical unit/scale/offset;
- qualifiers and endpoint fingerprint;
- health/unavailable state when a matching live inspection snapshot is supplied.

Search covers tool names, routes, providers, adapters, parameters, fields, semantic IDs, units,
methods, paths and aliases. Provider, adapter, method and side-effect filters are also available.

## Python API

```python
from schemarouter import (
    build_schema_explorer_document,
    render_schema_explorer,
)

document = build_schema_explorer_document(router.registry, live=router.inspect())
html = render_schema_explorer(document)
```

Use `write_schema_explorer(document, path)` to write the self-contained HTML directly.

A live snapshot is accepted only when its registry version and tool fingerprints exactly match the
registry snapshot used for the explorer. Mismatched operational state fails closed instead of being
shown against the wrong contract.

## Safety boundary

The explorer is documentation only.

It does **not** provide a "Try it out" or execution button. It never receives invokers, credential
values, request/response payloads, arbitrary ToolSpec metadata, or trace payloads.

The explorer document is built from an allowlisted inspection contract:

- provenance URLs are sanitized before rendering;
- arbitrary tool/endpoint metadata is excluded;
- authentication requirements contain scheme identity only, never credentials;
- all contract text and JSON are HTML-escaped before rendering.

If interactive execution is added in the future, it must use SchemaRouter's normal
validation/policy/approval path rather than bypassing runtime authority controls.

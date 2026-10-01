# Capability Explorer

SchemaRouter's **Capability Explorer** is the read-only documentation surface for the
registered typed capability catalog. It is protocol-neutral: OpenAPI, MCP, GraphQL,
OData, OpenRPC, OPTIMADE, Python, SDK-bound tools, and declarative HTTP capabilities
are presented through the same contract model.

## Static explorer from a persisted registry

```bash
schemarouter explorer \
  --registry ./schemarouter-registry.sqlite3 \
  --output ./schema-explorer.html
```

The generated HTML is self-contained and does not load remote JavaScript, CSS, fonts,
or other assets.

The explorer includes:

- tool/provider/adapter/source provenance;
- schema and endpoint fingerprints;
- read-only / mutating / destructive classification;
- authentication requirements without credential values;
- parameters, wire names, locations, serialization semantics, and JSON Schema;
- complete input/output schema views;
- output semantic IDs, units, normalization contracts, qualifiers, and projection paths;
- search across tools, endpoints, providers, fields, semantic IDs, units, methods, and modes.

Schema `default` / `example` / `examples` values are omitted from the explorer
document so documentation does not accidentally publish embedded example credentials
or other sample secrets. Arbitrary ToolSpec metadata is not copied into the explorer.

## Python API

```python
from schemarouter import (
    build_capability_explorer_document,
    render_schema_explorer,
)

document = build_capability_explorer_document(router.registry)
html = render_schema_explorer(document)
```

To include privacy-safe live binding, health, and schema-watch status:

```python
document = build_capability_explorer_document(
    router.registry,
    live=router.inspect(),
)
```

The explorer consumes only the canonical ToolSpec contract and the existing
privacy-safe RouterInspection snapshot. It never reads live invokers, credentials,
HTTP clients, subprocess handles, or arbitrary trace payload values.

## Security boundary

The explorer is documentation only.

It does **not** provide a Swagger-style "Try it out" execution button. Tool execution
continues to require SchemaRouter's normal planning, validation, policy, approval, and
binding checks.

The existing operational dashboard remains separate:

- **dashboard**: runtime/registry/run operational overview;
- **explorer**: detailed capability contract documentation.

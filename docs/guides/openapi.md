# OpenAPI

SchemaRouter can import a common, production-oriented subset of OpenAPI 3.x from JSON or YAML.

## Import

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

The adapter imports operations, path/query/header parameters, JSON request-body properties, response
schemas, local component references, and read/write classification inferred from the HTTP method.

## Same-origin and cross-origin servers

A same-origin runtime server can be bound automatically.

If the OpenAPI document declares a server on another origin, SchemaRouter imports the schema but
does not silently grant execution authority.

```python
router.bind_openapi(
    "users_api",
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

## Schema credentials versus runtime credentials

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    schema_headers={"X-Docs-Token": "..."},
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

`schema_headers` never become runtime API headers, and `trusted_headers` are never exposed as
model-selectable arguments.

## Parameter collisions

OpenAPI identifies parameters by both name and location. If an operation defines the same wire name
in multiple places, SchemaRouter creates distinct logical argument keys.

```text
path:id   -> path__id
query:id  -> query__id
header:id -> header__id
body:id   -> body__id
```

The transport maps those keys back to the original wire name.

## Local component references

Nested `#/components/...` references are preserved with their component root so runtime JSON Schema
validation can resolve them, including array item schemas.

## Current common subset

Supported paths include:

- OpenAPI 3.x JSON and YAML;
- operations under `paths`;
- path/query/header parameters;
- object-like JSON request bodies;
- JSON responses;
- local component references;
- explicit cross-origin binding;
- runtime origin confinement.

Richer external references, advanced composition, and more ergonomic non-object request bodies remain
post-v0.1 work. Unsupported constructs should not be guessed.


## Runtime response bound

OpenAPI runtime responses are streamed and capped at **16 MiB by default** before JSON/text decoding.
The bound applies even when a server omits or lies about `Content-Length`.

When constructing `OpenAPIRemoteInvoker` manually, trusted local code may choose a smaller or
larger positive integer through `max_response_bytes`. Keep the limit appropriate for the endpoint
contract; a high limit weakens protection against unexpectedly large remote responses.

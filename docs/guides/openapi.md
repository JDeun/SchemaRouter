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
schemas, local component references, local reference chains, local Path Item references, and
read/write classification inferred from the HTTP method. Object properties and required fields
reachable through `allOf` are flattened for planner visibility while the original composition is
retained for runtime JSON Schema validation. For response schemas, object fields reachable through
`oneOf` / `anyOf` variants are also exposed as conditional planner-visible output fields. The
original composed response schema remains authoritative at runtime.

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

## Typed JSON root request bodies

SchemaRouter keeps ordinary object request bodies ergonomic by flattening their declared properties
into named `body` parameters.

When an explicit JSON Schema cannot be flattened safely, the whole request payload is instead
represented as one typed `body` parameter. This covers:

- arrays;
- scalar JSON values;
- nullable/root `null` values;
- general `oneOf` / `anyOf` compositions;
- other explicit JSON Schema shapes that should remain intact.

For example, an array body:

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: array
        items:
          type: string
```

becomes:

```text
body: array[string]
```

The full value is validated locally against the original schema and transmitted as the JSON root.
SchemaRouter does not wrap it as `{"body": ...}`. JSON `null` is also emitted as the literal
`null` body rather than being mistaken for an omitted request.

A required root body that is absent fails closed before a network request is made.

## Discriminated JSON request bodies

SchemaRouter does not flatten arbitrary `oneOf` / `anyOf` request bodies because fields from
different variants could be combined into an invalid request. They are preserved as one typed root
`body` parameter instead.

For a strictly tagged `oneOf`, SchemaRouter additionally recognizes the discriminator contract
when:

- the schema declares `discriminator.propertyName`;
- every branch is object-like;
- every branch requires that discriminator property;
- every branch constrains it with a unique `const` or single-value `enum`.

Example:

```yaml
schema:
  oneOf:
    - $ref: '#/components/schemas/Cat'
    - $ref: '#/components/schemas/Dog'
  discriminator:
    propertyName: kind
```

The planner still sees one parameter carrying the original `oneOf` schema and discriminator
metadata. The body remains a single object through planning and validation. SchemaRouter validates the whole
object against the original composed JSON Schema, then the OpenAPI invoker sends that object as the
JSON request root. It never rewrites the payload as `{"body": ...}`.

This also works with a provider-neutral `ModelQueryAnalyzer`: an application-owned GPT, Gemini,
Claude, or other structured-output client may propose the complete `body` object, but unknown
arguments and schema-invalid variants are rejected locally before execution.

A discriminator mapping by itself is not sufficient. SchemaRouter requires the branch schemas to
prove their own unique tags so a stale or incorrect mapping cannot weaken the local contract.

## OpenAPI 3.0 nullable

OpenAPI 3.0 uses `nullable: true` instead of JSON Schema's `null` type. When `type` is declared
in the same Schema Object, SchemaRouter compiles the 3.0 semantics into an ordinary JSON Schema type
union:

```yaml
type: string
nullable: true
```

becomes:

```json
{"type": ["string", "null"]}
```

Other constraints remain authoritative. For example, an `enum` that omits `null` can still
reject `null`, matching OpenAPI 3.0's rule that other constraints retain their behavior.

Normalization is recursive through component schemas and the bounded external-reference bundle.
Examples/default values and arbitrary extension payloads are not rewritten.

A nullable object request body remains a typed root `body` rather than being flattened, because
the JSON root itself may legally be `null`.

OpenAPI 3.1 documents are not rewritten: they should express nullability with JSON Schema types,
for example `type: ["string", "null"]`.

## Parameter serialization

SchemaRouter compiles the OpenAPI default parameter styles into the endpoint contract and preserves
them in the schema fingerprint:

| Location | Supported style | Default explode | Supported values |
| --- | --- | ---: | --- |
| path | `simple` | `false` | scalar, array, object |
| query | `form` | `true` | scalar, array, object |
| header | `simple` | `false` | scalar, array, object |

Examples:

```text
path simple array:
  ["a", "b"] -> /a,b

query form array, explode=true:
  ["red", "blue"] -> ?tag=red&tag=blue

query form object, explode=false:
  {"role":"admin","active":true}
  -> ?filter=role,admin,active,true

header simple object, explode=true:
  {"role":"admin","active":true}
  -> X-Meta: role=admin,active=true
```

SchemaRouter deliberately fails closed for parameter serialization modes it does not yet emit
exactly, including non-default styles such as `matrix`, `label`, `spaceDelimited`,
`pipeDelimited`, and `deepObject`. Query parameters with `allowReserved: true` are also
rejected rather than silently changing reserved-character semantics.

The compatibility report exposes these cases before execution as `parameter_style` or
`allow_reserved` findings.

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

## Local and same-document references

Nested `#/components/...` reference chains are resolved for planner-side schema discovery while
their component root remains available to runtime JSON Schema validation, including array item
schemas and recursive structures.

When a document is loaded from a URL, URI references that resolve back to that exact document are
normalized to local JSON Pointer references. For example,
`./openapi.json#/components/schemas/User` is treated as a local reference when the loaded resource
is that same `openapi.json`.

SchemaRouter does **not** fetch cross-document references by default. Trusted callers may opt in to
bounded same-origin resolution:

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    openapi_external_refs=True,
)
```

The resolver follows relative/absolute HTTP(S) references only when they stay on the entry
document's origin. It reuses `schema_headers` only after this explicit opt-in and applies independent
limits for recursion depth, unique referenced documents, aggregate referenced bytes, per-document
bytes, and redirects.

Defaults:

```text
openapi_ref_max_depth      = 3
openapi_ref_max_documents  = 8
openapi_ref_max_bytes      = 10 MiB
per referenced document    = 5 MiB
redirects per document     = 5
```

These bounds can be reduced by trusted application code through the corresponding
`SchemaRouter.from_url()` / `add_url()` keyword arguments.

Referenced JSON/YAML documents are fetched completely, indexed as JSON Schema resources, rewritten
into a local in-memory bundle, and then consumed through the same local-ref parser and runtime JSON
Schema validator. This avoids fragment-only parsing and keeps execution schemas self-contained.

With `openapi_external_refs=True`, the bounded resolver understands static JSON Schema resource
scope:

- same-origin absolute or relative `$id` values rebase descendant `$ref` resolution;
- nested `$id` values are indexed as virtual resources inside the already loaded document;
- static `$anchor` fragments such as `schema.json#User` resolve to their indexed subschema;
- fetched/rebased resources remain confined to the entry document's origin;
- resolved `$ref` values are rewritten to local JSON Pointers;
- `$id` and `$anchor` are removed from the final runtime bundle after rewriting so validation
  does not trigger a second external-resolution path.

The current bounded resolver intentionally fails closed for:

- cross-origin referenced documents or cross-origin `$id` base URIs;
- `$id` values with fragments;
- missing, duplicate, or invalid static anchors;
- `$dynamicRef`, `$dynamicAnchor`, `$recursiveRef`, and `$recursiveAnchor`;
- depth/document/byte limit exhaustion;
- unstructured referenced content.

Dynamic JSON Schema scope is deliberately excluded because statically rewriting it as an ordinary
anchor could change validation semantics.

## Current common subset

Supported paths include:

- OpenAPI 3.x JSON and YAML;
- operations under `paths`;
- path/query/header parameters with spec-faithful default `simple` / `form` serialization;
- object-like JSON request bodies;
- JSON responses;
- local component/path-item reference chains;
- same-document URI-reference normalization;
- explicitly enabled bounded same-origin cross-document `$ref` bundling;
- bounded same-origin JSON Schema `$id` rebasing and static `$anchor` resolution;
- OpenAPI 3.0 `nullable: true` normalization when `type` is declared in the same Schema Object;
- planner-side object-property/required flattening through `allOf`;
- planner-visible response-field discovery across `oneOf` / `anyOf` object variants while
  preserving composed runtime validation;
- any explicit non-flattenable JSON request schema as one typed root-body parameter, including
  arrays, scalars, nullable roots, and composed `oneOf` / `anyOf` bodies;
- discriminator recognition for strictly tagged `oneOf` object bodies;
- explicit cross-origin binding;
- runtime origin confinement.

Dynamic JSON Schema references/anchors and automatic planner-side schema-variant selection remain
follow-up work. Variant request bodies stay intentionally unflattened even though they are
executable as one typed root body. Response variant
fields may be selected for projection, but a field that is absent from the actual validated
response variant is simply absent from the projected result. Unsupported constructs should not be
guessed.


## Runtime response bound

OpenAPI runtime responses are streamed and capped at **16 MiB by default** before JSON/text decoding.
The bound applies even when a server omits or lies about `Content-Length`.

When constructing `OpenAPIRemoteInvoker` manually, trusted local code may choose a smaller or
larger positive integer through `max_response_bytes`. Keep the limit appropriate for the endpoint
contract; a high limit weakens protection against unexpectedly large remote responses.

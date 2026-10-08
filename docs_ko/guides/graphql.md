# GraphQL

SchemaRouter can introspect a GraphQL endpoint and compile its root query and mutation fields into
the canonical `ToolSpec -> EndpointSpec -> ParameterSpec -> FieldSpec` model.

## GraphQL endpoint 등록

```python
router = await SchemaRouter.from_url(
    "https://api.example/graphql",
    kind="graphql",
)
```

SchemaRouter issues a bounded introspection query against the same URL and imports:

- root query fields as read-only endpoints;
- root mutation fields as non-read-only endpoints;
- field arguments as typed `ParameterSpec` values;
- object and input-object types as JSON Schema;
- nested output fields as planner-visible `FieldSpec` paths;
- enums as JSON Schema enum values.

Subscriptions are detected but not imported in the first implementation because they require a
long-lived stream lifecycle rather than an ordinary request/response `ToolCall`.

## Field selection을 GraphQL selection set으로 변환

If the plan asks for:

```text
id
metadata.source
```

SchemaRouter sends a selection equivalent to:

```graphql
query SchemaRouter($id: ID!) {
  material(id: $id) {
    id
    metadata {
      source
    }
  }
}
```

This is native server-side field projection, not a post-hoc payload filter.

When a selected field is itself a complex object and no descendant is selected explicitly,
SchemaRouter chooses a bounded default scalar/identifier selection rather than requesting the whole
subtree implicitly.

## Authority remains local

GraphQL schema introspection tells SchemaRouter whether a root field belongs to `Query` or
`Mutation`. This is used only to **narrow** authority:

- root query -> `read_only=True`;
- root mutation -> `read_only=False`.

Mutation descriptions, tags, or names never grant mutation permission. The default
`ExecutionPolicy` still denies mutations until trusted local policy allows them.

## Secrets

Authentication belongs to trusted runtime headers:

```python
router = await SchemaRouter.from_url(
    "https://api.example/graphql",
    kind="graphql",
    schema_headers={"Authorization": f"Bearer {schema_token}"},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)
```

These headers are not planner-selectable arguments and are not copied into the canonical tool
contract.

## Safety boundaries

- only HTTP(S) endpoints are accepted;
- redirects are not followed automatically;
- introspection and execution responses are size-bounded;
- recursive type traversal is depth-bounded;
- list fields use the same record-preserving item contract as other adapters; nested list children
  are named like `results[].title` while GraphQL selection sets remain normal
  `results { title }`;
- GraphQL execution errors fail the invocation;
- ordinary SchemaRouter input/output validation still applies after transport execution.

If a GraphQL service disables introspection, use a trusted local adapter/plugin or a declarative
contract rather than inferring the schema from arbitrary responses.

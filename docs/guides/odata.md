# OData

SchemaRouter can ingest an OData v4 service through its machine-readable `$metadata` CSDL document
and compile entity sets into the canonical capability model.

## Register an OData service

```python
router = await SchemaRouter.from_url(
    "https://services.example/odata",
    kind="odata",
)
```

You may also pass the metadata URL directly:

```python
router = await SchemaRouter.from_url(
    "https://services.example/odata/$metadata",
    kind="odata",
)
```

The adapter imports:

- entity sets as read-only endpoints;
- entity and complex-type properties as typed `FieldSpec` values;
- CSDL keys as identifier fields;
- common EDM scalar types as JSON Schema;
- `$filter`, `$orderby`, `$top`, and `$skip` as typed query arguments;
- nested complex properties as planner-visible dotted paths.

## Native server projection with `$select`

If a plan selects:

```text
ID
Address.City
```

SchemaRouter sends:

```text
$select=ID,Address/City
```

and then projects the returned records into the canonical result shape:

```json
[
  {
    "ID": 1,
    "Address.City": "Suwon"
  }
]
```

This keeps SchemaRouter's dotted internal field identity separate from OData's wire-level path
syntax.

## Authority and scope

The initial built-in adapter exposes **entity-set reads only**. OData actions and mutations are not
silently imported as executable write authority.

That is deliberate: `$metadata` describes interface shape, but execution authority remains a
trusted local decision.

## Authentication

Metadata-fetch and runtime credentials remain separate:

```python
router = await SchemaRouter.from_url(
    "https://services.example/odata",
    kind="odata",
    schema_headers={"Authorization": f"Bearer {metadata_token}"},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)
```

Secrets are never copied into planner-visible fields or arguments.

## Safety boundaries

- only HTTP(S) service roots are accepted;
- redirects are not followed automatically;
- metadata and response bodies are size-bounded;
- DTD/entity declarations in CSDL XML are rejected;
- nested complex traversal is depth-bounded;
- list/collection item traversal remains conservative;
- ordinary SchemaRouter input/output validation still runs;
- writes/actions require a separate explicit capability contract before execution.

Functions, actions, navigation expansion, and richer OData query semantics can be added
incrementally without changing the canonical `ToolSpec` model.

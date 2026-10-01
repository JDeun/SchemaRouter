# OData

SchemaRouter can ingest OData v4 CSDL metadata and compile entity sets into canonical typed
capabilities.

## Register a service

Pass either the service root or its `$metadata` URL:

```python
router = await SchemaRouter.from_url(
    "https://service.example/odata",
    kind="odata",
)
```

SchemaRouter fetches the CSDL metadata and imports entity types, complex types, entity keys, and
entity sets.

## Entity sets become read endpoints

An entity set such as `Products` becomes a read-only endpoint such as `list_products`.

Standard bounded query controls are exposed as typed parameters:

- `filter` -> `$filter`
- `orderby` -> `$orderby`
- `top` -> `$top`
- `skip` -> `$skip`

Write operations/actions are not granted automatically.

## Native field projection

OData's `$select` is used as server-side projection. If a plan asks for:

```text
ID
Address.City
```

the transport sends:

```text
$select=ID,Address/City
```

and SchemaRouter preserves record alignment while projecting each object in the returned
`value[]` collection.

Complex properties use planner-visible dotted identities while provider selectors use OData slash
notation.

Declared collections of complex values use the same record-preserving array-item contract as other
adapters. For example, `Measurements[].Value` uses the trusted path
`["Measurements", "*", "Value"]`, while the provider receives
`$select=Measurements/Value`. Multiple selected children remain grouped inside the same
`Measurements[]` records by index; SchemaRouter never flattens them into unrelated parallel arrays.

## Type and unit contracts

Common `Edm.*` primitives are mapped to JSON Schema, including strings/UUIDs, booleans, integer
families, decimal/floating-point numbers, dates/date-times, and collections. Entity keys become
identifier fields and complex types become nested object schemas.

Structured CSDL measure annotations are preserved when declared. In particular,
`Org.OData.Measures.V1.Unit` and `Org.OData.Measures.V1.ISOCurrency` values become
`FieldSpec.unit`.

SchemaRouter does not infer physical dimensions or conversion factors from those labels. Trusted
local enrichment remains responsible for normalization contracts.

## Credentials and security

Schema-fetch and runtime credentials stay separate:

```python
router = await SchemaRouter.from_url(
    "https://service.example/odata",
    kind="odata",
    schema_headers={"Authorization": schema_token},
    trusted_headers={"Authorization": runtime_token},
)
```

Neither credential set enters planner-visible contracts.

Additional boundaries:
- entity-set reads are explicitly read-only;
- actions/writes are not auto-enabled;
- redirects are not followed automatically;
- metadata and result sizes are bounded;
- DTD/entity declarations are rejected before XML parsing;
- ordinary SchemaRouter validation, fingerprints, health, fallback, and drift rules remain active.

## Scope

The initial first-class adapter covers entity-set reads, complex properties, paging/query controls,
structured unit annotations, and `$select`.

Functions/actions and richer OData query semantics can be added incrementally without changing the
canonical planner model.

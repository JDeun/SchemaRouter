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

SchemaRouter fetches:

```text
https://service.example/odata/$metadata
```

and imports entity types, complex types, entity keys, and entity sets.

## Entity sets become read endpoints

An entity set such as `Products` becomes a read-only endpoint like:

```text
list_products
```

Standard bounded query controls are exposed as typed parameters:

- `filter` -> `$filter`
- `orderby` -> `$orderby`
- `top` -> `$top`
- `skip` -> `$skip`

Write operations/actions are not granted automatically.

## Native field projection

OData's `$select` is used as server-side projection.

If the plan requests:

```text
ID
Address.City
```

the transport sends:

```text
$select=ID,Address/City
```

and SchemaRouter preserves record alignment when projecting the returned `value[]` collection.

Complex properties are represented with planner-visible dotted identities while the provider wire
selector uses OData slash notation.

## Type mapping

Common `Edm.*` primitive types are mapped to JSON Schema:

- strings and GUIDs;
- booleans;
- integer families;
- decimal/double/single numeric types;
- date/date-time values;
- collections.

Entity keys are marked as identifiers. Complex types become nested object schemas.

Structured CSDL measure annotations are preserved when declared. In particular,
`Org.OData.Measures.V1.Unit` and `Org.OData.Measures.V1.ISOCurrency` values become
`FieldSpec.unit`. SchemaRouter does not infer dimensions or conversion factors from those strings;
trusted enrichment remains responsible for normalization contracts.

## Trust and security

OData metadata describes data shape. It does not grant write authority.

- entity-set reads are explicitly read-only;
- actions/writes are not auto-enabled by the initial adapter;
- redirects are not followed automatically;
- metadata and result sizes are bounded;
- DTD/entity declarations are rejected before XML parsing;
- runtime credentials stay in trusted headers;
- ordinary SchemaRouter validation, fingerprints, health, fallback, and drift rules remain active.

## Scope

The initial first-class adapter covers entity-set reads, complex properties, paging/query controls,
and `$select`.

Functions/actions and richer OData query semantics can be added incrementally without changing the
canonical planner model.

# NoSQL record-store onboarding

SchemaRouter can expose non-relational record sources as typed bounded capabilities without
translating them into fake SQL or giving a model raw vendor query-DSL authority.

The common record-store contract covers four data models:

- document;
- search/index;
- key-value;
- time-series.

## Register a trusted backend

A vendor adapter or host-owned backend describes its sources and implements bounded queries:

```python
keys = router.add_record_store(
    backend,
    database_name="operations",
)
```

Async SDKs use:

```python
keys = await router.aadd_record_store(
    backend,
    database_name="operations",
)
```

Each discovered source declares:

- source name and data model;
- output fields and their JSON-schema types;
- identifier fields;
- fields that allow exact-match filtering;
- optional plain-text search support;
- optional time field;
- explicitly public metadata.

## Query boundary

The generated `query` capability is deliberately limited.

Depending on the source declaration it may expose:

- optional plain-text `query`;
- exact-match `filter__<field>` parameters only for declared filterable/identifier fields;
- optional `start_time` / `end_time` for declared time-series sources;
- bounded `limit`;
- explicit output-field projection.

There is no model-visible MongoDB query document, Elasticsearch/OpenSearch Query DSL, Redis command,
DynamoDB expression, or other arbitrary vendor command surface.

Vendor adapters translate the bounded contract into native SDK calls inside trusted runtime state.

## Authorization

Each collection/index/keyspace/series is a separate capability and therefore composes with
principal-aware authorization.

For example, employees can see general document collections while an executive collection remains
non-disclosed:

```python
AuthorizationRule(
    effect="allow",
    operation="nosql.documents.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="nosql.executive_docs.*",
    roles_any=("executive",),
)
```

Field/tenant predicates that must never be overridden by model arguments are extended in #770.

## Vendor targets

The provider-neutral contract is designed for thin adapters around commonly deployed systems such
as:

- MongoDB and Couchbase for document data;
- Elasticsearch / OpenSearch for search indexes;
- Redis, DynamoDB, and Cosmos DB for key-value/document access;
- InfluxDB and compatible time-series sources;
- vendor-specific sources that can express the same bounded record contract.

ClickHouse and other SQL-capable analytical stores may use the SQLAlchemy database path when that
is the safer and more natural contract.

The common contract does **not** mean every vendor SDK has already completed native/live acceptance.
Vendor adapters and live acceptance remain explicit follow-up work under #769.

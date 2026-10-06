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

There is no model-visible MongoDB query document, Elasticsearch/OpenSearch Query DSL,
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

Field/tenant predicates that must never be overridden by model arguments are enforced through
principal DataScope trusted filters and are revalidated at execution.

## Native vendor adapters

The bounded record contract now has caller-owned native adapters for:

- **MongoDB**: collection discovery, sampled document schema, bounded `find()`, optional configured text/time paths;
- **Elasticsearch / OpenSearch**: mapping discovery, bounded `multi_match`/term/range queries and field projection;
- **Amazon DynamoDB**: table/key discovery, sampled fields, parameterized filter/projection expressions;
- **Azure Cosmos DB for NoSQL**: container discovery, sampled item schema and parameterized `query_items()`;
- **Couchbase**: keyspace discovery and bounded named-parameter SQL++ queries;
- **ClickHouse**: table/column discovery and bound read-only ClickHouse Connect queries;
- **InfluxDB 2.x / Flux**: measurement, field-key and tag-key discovery with bounded time/tag/field queries.

For schemaless MongoDB collections, non-key DynamoDB attributes, Cosmos DB containers, and
Couchbase keyspaces, discovery is explicitly **partial** rather than authoritative. SchemaRouter
processes at most 16 sampled records and at most 256 KiB of sample payload per source, unions fields
observed across those records, and only declares a sampled field type when repeated non-null
observations agree. DynamoDB key attribute types still use authoritative `DescribeTable` metadata.
A field seen once, an unknown value type, or heterogeneous observed types therefore remain
unconstrained instead of being narrowed from one arbitrary document.

The generated source metadata exposes `public_metadata.schema_discovery` with
`complete=false`, the observed sample count, and the configured row/byte bounds. Callers and
authorization layers can therefore distinguish sampled catalogs from provider-authoritative
schemas. A later refresh may safely expand the discovered field set as new records become visible;
earlier samples are never presented as proof that the source schema was complete.

Typical registration remains caller-owned:

```python
router.add_mongodb_record_store(mongo_database)
router.add_elasticsearch_record_store(elastic_client)
router.add_opensearch_record_store(opensearch_client)
router.add_dynamodb_record_store(dynamodb_client)
router.add_cosmos_record_store(cosmos_database)
router.add_couchbase_record_store(couchbase_cluster)
router.add_clickhouse_record_store(clickhouse_client)
router.add_influxdb_record_store(
    influx_query_api,
    bucket="metrics",
    org="acme",
)
```

SchemaRouter stores none of those clients or credentials in model-visible contracts. Native
adapters translate only the already bounded record-store surface; raw Mongo query documents,
Elasticsearch/OpenSearch Query DSL, Dynamo expressions, Cosmos SQL, SQL++, raw
ClickHouse SQL, and arbitrary Flux remain outside model authority.

Deterministic SDK-shape tests are release-gated. Native adapter availability is distinct from
external live acceptance for every vendor/version/deployment.

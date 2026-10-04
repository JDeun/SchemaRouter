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

## Native vendor adapters

The bounded record contract now has caller-owned native adapters for:

- **MongoDB**: collection discovery, sampled document schema, bounded `find()`, optional configured text/time paths;
- **Elasticsearch / OpenSearch**: mapping discovery, bounded `multi_match`/term/range queries and field projection;
- **Amazon DynamoDB**: table/key discovery, sampled fields, parameterized filter/projection expressions;
- **Azure Cosmos DB for NoSQL**: container discovery, sampled item schema and parameterized `query_items()`;
- **Couchbase**: keyspace discovery and bounded named-parameter SQL++ queries;
- **ClickHouse**: table/column discovery and bound read-only ClickHouse Connect queries;
- **InfluxDB 2.x / Flux**: measurement, field-key and tag-key discovery with bounded time/tag/field queries.

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

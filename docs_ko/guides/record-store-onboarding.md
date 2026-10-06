# NoSQL record-store 등록

SchemaRouter는 비관계형 데이터를 가짜 SQL로 억지 변환하거나 모델에 vendor query DSL을 직접
실행시키지 않고 typed bounded capability로 노출할 수 있습니다.

공통 record-store contract는 네 데이터 모델을 다룹니다.

- document
- search/index
- key-value
- time-series

## Trusted backend 등록

Vendor adapter 또는 host-owned backend가 source schema를 기술하고 bounded query를 구현합니다.

```python
keys = router.add_record_store(
    backend,
    database_name="operations",
)
```

Async SDK는 다음을 사용합니다.

```python
keys = await router.aadd_record_store(
    backend,
    database_name="operations",
)
```

각 source가 선언하는 항목은 다음과 같습니다.

- source 이름과 data model
- output field와 JSON-schema type
- identifier field
- exact-match filter를 허용할 field
- optional plain-text search
- optional time field
- 명시적으로 공개할 metadata

## Query 경계

생성되는 `query` capability는 의도적으로 제한됩니다.

Source 선언에 따라 다음만 노출됩니다.

- optional plain-text `query`
- 선언된 filterable/identifier field의 exact-match `filter__<field>`
- time-series의 optional `start_time` / `end_time`
- bounded `limit`
- explicit output-field projection

모델에 MongoDB raw query document, Elasticsearch/OpenSearch Query DSL,
DynamoDB expression 등의 arbitrary vendor command를 직접 전달하는 surface는 없습니다.

Vendor adapter가 bounded contract를 trusted runtime 안에서 native SDK call로 번역합니다.

## 권한관리

각 collection/index/keyspace/series가 별도 capability이므로 principal-aware authorization을
그대로 적용할 수 있습니다.

예를 들어 일반 문서 collection은 사원에게 공개하고 executive collection은 임원에게만
보이게 할 수 있습니다.

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

모델 argument가 덮어쓸 수 없는 field/tenant predicate는 principal DataScope의 trusted filter로
적용하고 실행 시점에 다시 검증합니다.

## Native vendor adapter

Bounded record contract 위에 caller-owned native adapter를 추가합니다.

- **MongoDB**: collection discovery, sample document schema, bounded `find()`, 선택적 text/time 경로
- **Elasticsearch / OpenSearch**: mapping discovery, bounded `multi_match`/term/range, field projection
- **Amazon DynamoDB**: table/key discovery, sample field, parameterized filter/projection expression
- **Azure Cosmos DB for NoSQL**: container discovery, sample item schema, parameterized `query_items()`
- **Couchbase**: keyspace discovery와 named-parameter SQL++ bounded query
- **ClickHouse**: table/column discovery와 bound read-only ClickHouse Connect query
- **InfluxDB 2.x / Flux**: measurement/field-key/tag-key discovery와 bounded time/tag/field query

Schema가 고정되지 않은 MongoDB collection, DynamoDB의 non-key attribute, Cosmos DB container,
Couchbase keyspace는 discovery 결과를 authoritative schema가 아닌 명시적인 **partial schema**로
취급합니다. SchemaRouter는 source마다 최대 16개 record, 최대 256 KiB의 sample payload만
처리하고, 여러 record에서 관찰한 field를 union합니다. Sample에서 추론한 field type은 두 번
이상의 non-null 관찰이 모두 같은 type일 때만 선언합니다. DynamoDB key attribute type은
계속 authoritative한 `DescribeTable` metadata를 사용합니다. 따라서 한 record에서만 보인
field, 알 수 없는 value type, 서로 다른 type으로 관찰된 field는 임의의 단일 document에
맞춰 좁히지 않고 unconstrained schema로 유지합니다.

생성된 source metadata의 `public_metadata.schema_discovery`에는 `complete=false`, 실제
sample count, row/byte bound가 기록됩니다. 따라서 caller와 authorization layer는 sampled
catalog와 provider-authoritative schema를 구분할 수 있습니다. 이후 refresh에서 새로운
record가 관찰되면 field set이 안전하게 확장될 수 있으며, 이전 sample을 전체 source schema가
완전했다는 근거로 취급하지 않습니다.

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

이 client/credential은 model-visible contract에 저장하지 않습니다. Native adapter는 이미
제한된 record-store contract만 vendor API로 번역하며 raw Mongo query document,
Elasticsearch/OpenSearch Query DSL, Dynamo expression, Cosmos SQL, SQL++, raw
ClickHouse SQL, arbitrary Flux를 모델 권한으로 노출하지 않습니다.

Deterministic SDK-shape test는 release gate에 포함합니다. Native adapter가 있다는 사실과 모든
vendor/version/deployment의 외부 live acceptance가 끝났다는 주장은 구분합니다.

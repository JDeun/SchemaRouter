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
- **Elasticsearch / OpenSearch**: 매핑 자동 탐색, 제한된 `multi_match`·term·range 검색, 필드 투영
- **Amazon DynamoDB**: 테이블·키 탐색, 표본 필드, 매개변수화한 필터·투영 표현식
- **Azure Cosmos DB for NoSQL**: 컨테이너 탐색, 표본 항목 스키마, 매개변수화한 `query_items()`
- **Couchbase**: keyspace discovery와 named-parameter SQL++ bounded query
- **ClickHouse**: table/column discovery와 bound read-only ClickHouse Connect query
- **InfluxDB 2.x / Flux**: measurement/field-key/tag-key discovery와 bounded time/tag/field query

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
Elasticsearch/OpenSearch Query DSL, DynamoDB 표현식, Cosmos SQL, SQL++, 원시 ClickHouse SQL 또는 임의의 Flux 쿼리를 모델에 실행 권한으로 노출하지 않습니다.

Deterministic SDK-shape test는 release gate에 포함합니다. Native adapter가 있다는 사실과 모든
vendor/version/deployment의 외부 live acceptance가 끝났다는 주장은 구분합니다.
## Schemaless discovery는 의도적으로 partial입니다

MongoDB, DynamoDB, Cosmos DB, Couchbase는 완전한 authoritative field schema 없이 서로 다른
형태의 record를 저장할 수 있습니다. 따라서 native adapter는 최대 16개 record만 확인하고,
sample materialization이 256 KiB 또는 로컬 iteration 5초에 도달하면 중단합니다. SDK가 허용하는
경우에는 stable order 또는 provider-side execution bound도 함께 사용합니다.

발견되는 field set은 이 bounded sample들의 결정적인 합집합입니다. Record 값에서만 추론한 type은
관찰된 한 runtime type을 authoritative contract로 승격하지 않고 `{}`로 유지합니다. DynamoDB key
attribute type과 Cosmos DB의 `id`처럼 provider metadata가 제공하는 정보만 authoritative type으로
사용합니다. Endpoint의 `public_metadata.schema_discovery`에는 `partial` 상태와 고정 discovery
bound가 명시됩니다.

이후 refresh에서 새 field가 bounded sample에 들어오면 field set이 확장될 수 있습니다. Sample 값의
type을 좁히지 않으므로 heterogeneous value 때문에 type만 바뀌는 fingerprint oscillation은 막습니다.
Authorization에서는 계속 선언된 field만 addressable한 것으로 취급해야 하며, 완전한 field contract가
필요한 호스트는 sample discovery 대신 authoritative backend/schema를 제공해야 합니다.


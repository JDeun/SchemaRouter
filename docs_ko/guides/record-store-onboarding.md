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

모델에 MongoDB raw query document, Elasticsearch/OpenSearch Query DSL, Redis command,
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

모델 argument가 절대로 덮어쓸 수 없는 field/tenant predicate는 #770에서 확장합니다.

## Vendor 대상

Provider-neutral contract 위에 다음 계열의 thin adapter를 붙이는 구조입니다.

- MongoDB / Couchbase: document
- Elasticsearch / OpenSearch: search index
- Redis / DynamoDB / Cosmos DB: key-value 또는 document
- InfluxDB 및 호환 계열: time-series
- 동일 bounded record contract를 표현할 수 있는 기타 vendor source

ClickHouse처럼 SQL contract가 더 자연스러운 분석 DB는 SQLAlchemy 경로를 사용할 수 있습니다.

공통 contract가 있다는 것만으로 모든 vendor SDK의 native/live acceptance가 끝났다는 뜻은
아닙니다. Vendor adapter와 live acceptance는 #769에서 별도 추적합니다.

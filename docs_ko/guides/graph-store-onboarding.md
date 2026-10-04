# Graph / RDF 등록

SchemaRouter는 모델에 arbitrary Cypher, Gremlin, SPARQL 실행 권한을 주지 않고 property graph와
RDF source를 typed bounded traversal capability로 노출할 수 있습니다.

## Provider-neutral graph contract

Trusted graph adapter가 graph schema를 discover하고 bounded traversal을 구현합니다.

```python
keys = router.add_graph_store(
    backend,
    database_name="knowledge",
)
```

Async backend는 다음을 사용합니다.

```python
keys = await router.aadd_graph_store(
    backend,
    database_name="knowledge",
)
```

Discovery가 기술하는 항목은 다음과 같습니다.

- graph/source 이름
- graph model: `property_graph` 또는 `rdf`
- node label/class/type
- relationship type 또는 RDF predicate
- model-visible property
- 명시적으로 공개한 graph metadata

SchemaRouter는 graph별 typed `traverse` capability로 컴파일합니다.

## Bounded traversal

모델에 노출되는 traversal surface는 의도적으로 제한합니다.

- 필수 `start_id`
- relationship/predicate는 discover된 schema 안에서만 선택
- direction은 `out`, `in`, `both`
- bounded `max_hops`
- bounded result count
- 명시적인 output field projection

모델이 임의 Cypher/Gremlin/SPARQL 문자열을 전달하는 parameter는 없습니다.

Vendor adapter가 이 bounded contract를 native driver call로 번역합니다.

## 권한관리

각 graph가 별도 capability이므로 principal-aware authorization으로 retrieval 전에 graph 자체를
숨길 수 있습니다.

```python
AuthorizationRule(
    effect="allow",
    operation="knowledge.org.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="knowledge.executive.*",
    roles_any=("executive",),
)
```

권한 없는 graph capability는 model selection 전에 non-disclosure 처리하고 실행 전 다시
검증합니다.

Node/property/relationship visibility, 허용 relationship 집합, 최대 traversal depth는 principal
DataScope rule로 적용하고 실행 시점에 다시 검증합니다.

## Native vendor adapter

Provider-neutral contract 위에 caller-owned native adapter가 추가됩니다.

- **Neo4j**: Python driver의 `execute_query()` 경계
- **Amazon Neptune Database / Neptune Analytics**: 지원되는 openCypher Data API
- **ArangoDB**: `python-arango` graph discovery와 parameter-bound AQL traversal
- **FalkorDB**: 공식 caller-owned Python client의 `GRAPH.LIST`/`ro_query()` 기반 openCypher discovery와 read-only traversal
- **SPARQL 1.1 query endpoint**: caller-owned HTTP client를 사용하며 GraphDB/Stardog 계열과
  같은 호환 RDF store에 연결 가능

```python
router.add_neo4j_graph(driver, database="neo4j", graph_name="org")
router.add_neptune_graph(neptune_client, graph_name="social")
router.add_arango_graph(arango_database)
router.add_falkordb_graph(falkordb_client, graphs={"social"})
router.add_sparql_graph(
    http_client,
    endpoint="https://example.org/sparql",
    graph_name="rdf",
)
```

이 adapter들은 SchemaRouter의 bounded traversal contract만 native 호출로 번역합니다.
모델 출력에 raw Cypher, AQL, Gremlin, SPARQL 문자열 실행 권한을 주지 않습니다. FalkorDB adapter는 graph 이름, label, relationship type, 공개 가능한 property 이름을 탐색하고 실행은 `ro_query()`로만 제한합니다.

Deterministic SDK-shape test는 release gate에 포함합니다. Native adapter가 존재한다는 사실과
모든 vendor/version/deployment의 외부 live acceptance가 완료됐다는 주장은 구분합니다.

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

Node/property/relationship 세부 scope와 trusted traversal predicate는 #770에서 확장합니다.

## Vendor 대상

Provider-neutral contract 위에 다음 계열의 thin adapter를 붙이는 구조입니다.

- Neo4j
- Amazon Neptune
- ArangoDB
- GraphDB/Stardog 계열을 포함한 호환 SPARQL 1.1 endpoint

먼저 공통 contract를 구현하고 native vendor SDK/live acceptance는 별도 vendor-adapter 단계로
진행합니다. 따라서 공통 contract가 있다는 것만으로 위 모든 DB의 end-to-end 검증이 끝났다는
뜻은 아닙니다.

# RAG와 에이전트를 위한 구조화된 retrieval/execution

**RAG (Retrieval-Augmented Generation)** 는 외부 source에서 가져온 정보를 사용해 모델 생성
과정을 보강하는 아키텍처입니다.

SchemaRouter 자체가 RAG는 아닙니다. 다만 외부 정보가 OpenAPI endpoint, MCP tool, OPTIMADE
service, typed Python callable 같은 **구조화된 실행 source**에 있을 때 retrieval/execution 경계의
일부를 담당할 수 있습니다.

```mermaid
flowchart LR
    Q["사용자 질문"] --> A["RAG / agent / application"]
    A --> SR["SchemaRouter"]
    SR --> R["registered capability retrieval"]
    R --> F["endpoint + field selection"]
    F --> V["policy / health / parameter validation"]
    V --> E["trusted execution"]
    E --> D["typed external data"]
    D --> A
```

## 작은 candidate set을 agent에 넘기기

```python
candidates = router.retrieve(
    "current Young's modulus for MAT-7",
    k=5,
)

for item in candidates.candidates:
    print(item.route_id, item.score)
    for field in item.output_fields:
        print(field.semantic_id, field.json_schema, field.unit)
```

현재 실행 가능한 binding까지 준비된 route만 원하면:

```python
router.retrieve_executable("current Young's modulus for MAT-7", k=5)
```

비동기 API는 `aretrieve`, `aretrieve_executable`입니다.

Retrieval 결과는 full effective input/output JSON Schema, parameter, output field, semantic ID,
unit, qualifier, side-effect classification, provider/access identity, fingerprint를 보존합니다.

중요한 점은 **retrieval이 execution authority가 아니라는 것**입니다.

```text
query
  -> SchemaRouter Top-K registered candidates
  -> downstream agent chooses
  -> local validation / policy
  -> execution
```

## Capability는 실행 계약입니다

문서 retriever가 context chunk를 반환한다면 SchemaRouter는 등록된 **executable contract**를
반환합니다.

```text
Endpoint
  operation
  input contract
  output fields
  read/write/destructive semantics
  provider/access identity
  availability
  policy/evidence requirements
```

모델은 등록된 후보를 rank/veto하는 데 도움을 줄 수 있지만 새 endpoint, field, permission,
credential, health state를 만들 수 없습니다.

## Field-first, route-second

```text
"What is the elastic modulus of this material?"
        ↓
semantic field = elastic_modulus
        ↓
provider A / REST
provider A / OPTIMADE
provider B / MCP
```

Availability나 policy 때문에 route는 바뀔 수 있지만 **요청된 field contract 자체는 바뀌면 안
됩니다**.

## Datatype / unit / qualifier

같은 이름의 field라고 자동으로 같은 의미가 되지는 않습니다.

예:

```text
semantic_id: mechanical.elastic_modulus
type: number
source_unit: GPa
canonical_unit: Pa
dimension: pressure
qualifiers:
  temperature: 300 K
  phase: alpha
```

Cross-provider fallback은 semantic field, datatype/shape, unit normalization contract, qualifier
compatibility를 보수적으로 확인합니다. SchemaRouter는 unit 문자열만 보고 conversion factor나
과학적 동등성을 추론하지 않습니다.

Unit은 optional입니다. 문자열, identifier, boolean, metadata, dimensionless number는 unit이
없을 수 있습니다.

## 범용 registration

새 OpenAPI/MCP/Python source가 들어오면 같은 typed registry contract로 컴파일되어야 합니다.

```text
new source
  -> parse declared schema
  -> compile typed registry
  -> update indexes
  -> bounded routing
```

새 route를 쓰기 위해 route-specific classifier를 따로 만들어야 하는 구조를 목표로 하지 않습니다.

## 경계

상위 계층은 conversation, decomposition, memory, graph, final answer generation을 소유합니다.
SchemaRouter는 더 좁은 질문에 답합니다.

> 등록된 capability 중에서 이 요청을 만족할 수 있는 가장 작은 trusted executable data surface는 무엇인가?

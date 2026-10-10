# Enterprise data onboarding

SchemaRouter는 사내·외부 데이터 시스템을 typed capability로 등록하되, 사용자 인증,
credential, network access, DB-native permission은 host application이 계속 소유하도록
설계되어 있습니다.

Enterprise data 경계는 다음과 같습니다.

```text
검증된 principal + caller-owned data client
        ↓
schema / collection / graph discovery
        ↓
principal-aware capability visibility
        ↓
trusted row / tenant / relationship scope
        ↓
bounded read-only execution
        ↓
projected typed result
```

SchemaRouter가 사용자를 인증하거나 DB credential을 저장하거나 범용 query proxy가 되는 구조는
아닙니다.

## 지원 데이터 계열

| 계열 | Core onboarding 경로 | Native coverage |
| --- | --- | --- |
| 관계형 / warehouse | SQLite 또는 caller-owned SQLAlchemy Engine | SQLite + SQLAlchemy dialect ecosystem |
| Vector | provider-neutral vector contract | Qdrant, Milvus, Pinecone, Weaviate, Chroma, PostgreSQL/pgvector |
| Graph / RDF | provider-neutral graph contract | Neo4j, Neptune, ArangoDB, FalkorDB, SPARQL |
| Document / search / KV / time-series | provider-neutral record contract | MongoDB, Elasticsearch/OpenSearch, DynamoDB, Cosmos DB, Couchbase, ClickHouse, InfluxDB |

일반 Redis record/vector/search를 first-class core surface로 제공하지는 않습니다. FalkorDB는
Redis 일반 기능과 별개로 graph capability contract를 통해 graph DB로 지원합니다.

Vendor client와 connection pool은 caller-owned 상태로 남고 SchemaRouter는 agent/application에
필요한 bounded schema와 execution surface만 등록합니다.

## Schema 자동 파악

관계형 DB는 table, view, column, primary key를 reflection합니다. 다른 계열은 각 데이터 모델의
native schema를 사용합니다.

- 벡터 컬렉션·인덱스·차원·거리 측정 기준·메타데이터 필드
- 그래프 레이블·클래스·관계·술어 타입·속성·탐색 깊이 제한
- 문서·검색 매핑·키 필드·필터 가능한 필드·텍스트·시간 검색 기능

Schema discovery 자체가 실행 권한을 만들지는 않습니다. 등록된 capability도 실행 직전에
authorization, binding, argument, output validation을 다시 통과해야 합니다.

## 사용자·직급·부서·팀별 접근 범위

Host application이 검증한 `PrincipalContext`를 넘기면 SchemaRouter가 role, department,
team, trusted attribute를 RBAC/ABAC 규칙으로 조합할 수 있습니다.

```python
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    PrincipalContext,
    TrustedFilterBinding,
)

policy = AuthorizationPolicy(
    rules=(
        AuthorizationRule(
            effect="allow",
            operation="company.employees.*",
            roles_any=("employee", "manager", "executive"),
        ),
    ),
    data_rules=(
        DataScopeRule(
            operation="company.employees.select",
            roles_any=("employee",),
            visible_fields=("id", "name"),
            trusted_filters=(
                TrustedFilterBinding(
                    field="department",
                    principal_value="attribute:department",
                ),
            ),
        ),
    ),
)

principal = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes=(("department", "platform"),),
)
```

권한이 없는 capability는 모델에 보이기 전에 제거하고 실행 직전 다시 확인합니다.
Principal에서 나온 trusted filter는 모델 argument로 제거하거나 범위를 넓힐 수 없습니다.

## 데이터 계열별 scope

| 계열 | Principal-aware scope |
| --- | --- |
| 관계형 | table visibility, visible column, trusted equality/IN row filter |
| Vector | collection visibility, result field, trusted metadata filter |
| Document/search/KV/time-series | source visibility, projected field, trusted exact-match filter |
| Graph/RDF | graph visibility, projected field, 허용 relationship/predicate, 최대 hop |

DB-native role, grant, RLS, ACL, tenant credential, network control은 계속 최종 권한 경계입니다.
SchemaRouter는 그 권한을 더 좁힐 수는 있지만 넓혀서는 안 됩니다.

## Read-only 실행 경계

Core enterprise data adapter는 vendor raw query language 대신 bounded operation을 노출합니다.

관계형 adapter는 모델이 만든 arbitrary SQL을 받지 않습니다. Vector adapter는 raw query object를
노출하지 않습니다. Record adapter는 Mongo/Elasticsearch/Dynamo/Cosmos/Flux command language를
모델 권한으로 주지 않습니다. Graph adapter도 arbitrary Cypher/AQL/Gremlin/SPARQL text를
모델이 직접 실행하게 하지 않습니다.

즉 schema discovery와 query authority를 분리합니다.

## 세부 문서

- [관계형 DB onboarding](database-onboarding.md)
- [Vector store onboarding](vector-store-onboarding.md)
- [Graph / RDF onboarding](graph-store-onboarding.md)
- [NoSQL record-store onboarding](record-store-onboarding.md)
- [Principal 기반 권한관리](authorization.md)

DB가 아니라 provider/API 시스템을 연결하려면
[Provider-first registration](provider-first-registration.md)을 참고하세요.

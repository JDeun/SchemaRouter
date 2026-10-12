# 데이터베이스 등록과 스키마 자동 파악

SchemaRouter는 연결 객체, 인증 정보, 임의의 쿼리 문자열을 모델에 노출하지 않으면서 데이터베이스를 타입이 명시된 기능의 공급원으로 사용할 수 있습니다.

DB 계층도 provider-first와 같은 경계를 따릅니다.

```text
caller-owned connection / engine
        ↓
trusted schema introspection
        ↓
ToolSpec / EndpointSpec / FieldSpec
        ↓
principal-aware retrieval
        ↓
bounded read-only invoker
        ↓
database-native authorization
```

SchemaRouter 자체가 데이터베이스 프록시나 IAM(신원 및 접근 관리) 시스템이 되는 것은 아닙니다. 인증, 비밀 정보, 연결 풀 및 데이터베이스 고유 역할의 관리는 호스트 애플리케이션이 담당합니다.

## SQLite reference 경로

SQLite는 추가 dependency가 필요 없는 reference implementation입니다.

```python
import sqlite3

from schemarouter import SchemaRouter

connection = sqlite3.connect("/srv/app/company.db")

router = SchemaRouter()
keys = router.add_sqlite_database(
    connection,
    database_name="company",
    tables={"employee_directory", "orders"},
)
```

선택한 table/view를 introspect해 다음을 자동 생성합니다.

- table/view별 typed tool
- column 기반 field
- primary key가 있으면 exact-match parameter
- bounded `limit` / `offset`
- projected read-only `select`

모델에 보이는 `sql`, `where`, raw-query parameter는 없습니다.

실제 `sqlite3.Connection`은 trusted invoker 내부에만 남습니다.

## SQLAlchemy Engine

Optional database integration을 설치합니다.

```bash
pip install "schemarouter[database]"
```

이후 caller-owned SQLAlchemy Engine을 전달합니다.

```python
from sqlalchemy import create_engine

from schemarouter import SchemaRouter

engine = create_engine(DATABASE_URL)

router = SchemaRouter()
keys = router.add_sqlalchemy_database(
    engine,
    database_name="erp",
    schemas=["public"],
    tables={"orders", "customers"},
)
```

Dialect별 reflection과 parameter binding은 SQLAlchemy가 담당합니다. Engine URL, password,
driver state, pool, live connection은 ToolSpec metadata로 복사되지 않습니다.

공통 SQLAlchemy 경로는 정상적인 dialect/driver가 있는 PostgreSQL, MySQL/MariaDB,
Microsoft SQL Server, Oracle, SQLite와 주요 warehouse 계열을 같은 계약으로 연결하기 위한
구조입니다. 이는 **해당 방언(dialect)을 지원할 수 있는 아키텍처**를 뜻할 뿐, 모든 벤더에서 실제 연결·동작 검증을 완료했다는 의미는 아닙니다.

## 권한관리

DB tool은 `PrincipalContext`와 `AuthorizationPolicy`를 그대로 사용합니다.

예를 들어 일반 사원은 directory view만, 관리자는 직원 원본 table까지, 임원은 board finance
table까지 보도록 구성할 수 있습니다.

```python
AuthorizationRule(
    effect="allow",
    operation="company.employee_directory.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="company.employees.*",
    roles_any=("manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="company.board_financials.*",
    roles_any=("executive",),
)
```

권한 없는 relation은 모델에 전달되기 전 retrieval 단계에서 제거하고 실행 직전 다시
검증합니다.

데이터베이스 자체의 역할(role), 권한 부여(grant), 행 수준 보안(RLS), 접근 제어 목록(ACL)이 최종 권한 경계입니다. SchemaRouter 정책은 데이터베이스 계정에 원래 부여된 권한을 제한할 수는 있지만 확대할 수는 없습니다.

## 현재 query 경계

첫 DB execution surface는 의도적으로 좁습니다.

- read-only
- 명시적인 output-field projection
- introspect한 primary-key column의 exact-match filter
- bounded limit/offset
- parameterized execution
- 모델이 생성한 arbitrary SQL 금지
- DDL/DML 금지

즉 schema discovery와 query authority를 분리합니다.

## 현재 DB family 지원 범위

서로 다른 DB 계열을 억지로 SQL 하나로 통일하지 않고 각 데이터 모델의 native execution
방식을 유지합니다.

| 계열 | 현재 core 경로 |
| --- | --- |
| SQLite | stdlib introspection + bounded SELECT |
| RDB / warehouse | caller-owned SQLAlchemy Engine + dialect reflection |
| Vector | 공통 contract + Qdrant, Milvus, Pinecone, Weaviate, Chroma, PostgreSQL/pgvector adapter |
| Property graph / RDF | 공통 contract + Neo4j, Neptune, ArangoDB, FalkorDB, SPARQL adapter |
| Document / search / key-value / time-series | 공통 contract + MongoDB, Elasticsearch/OpenSearch, DynamoDB, Cosmos DB, Couchbase, ClickHouse, InfluxDB adapter |
| DB 전 계열 권한 | capability, field, row/tenant, collection/source, relationship, hop scope 공유 |

계열 전체 구조는 [Enterprise data onboarding](enterprise-data-onboarding.md)을 참고하고,
벤더별 동작은 vector/graph/record-store 가이드를 참고하세요.

여기서 '지원'이란 핵심 패키지에 어댑터와 범위가 제한된 계약이 존재한다는 뜻입니다. 실제 외부 환경에서의 수용 시험 통과 여부는 벤더·버전·배포 환경마다 다르며 별도로 보고합니다.

벤더별 credential과 client object는 SchemaRouter의 model-visible graph에 넣지 않고
adapter/plugin 뒤의 trusted runtime state로 유지합니다.

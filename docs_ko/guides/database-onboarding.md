# 데이터베이스 등록과 스키마 자동 파악

SchemaRouter는 connection object, credential, arbitrary query string을 모델에 노출하지 않고
DB를 typed capability source로 다룰 수 있습니다.

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

SchemaRouter가 DB proxy나 IAM 서버가 되는 것은 아닙니다. 인증, secret, connection pool,
native database role은 host application이 소유합니다.

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
구조입니다. 이는 **dialect 지원 구조**를 뜻하며 모든 벤더의 live acceptance가 이미 끝났다는
의미는 아닙니다.

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

DB 자체의 role, grant, RLS, ACL은 계속 최종 권한 경계입니다. SchemaRouter는 DB 계정이 가진
권한을 더 좁힐 수는 있지만 넓혀서는 안 됩니다.

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

## DB family 확장 계획

서로 다른 DB를 억지로 SQL 하나로 통일하지 않습니다.

| 계열 | 구조 | 상태 |
| --- | --- | --- |
| SQLite | stdlib introspection + bounded SELECT | reference implementation |
| RDB / warehouse | caller-owned SQLAlchemy Engine | generic adapter 구현, vendor live acceptance는 별도 확대 |
| Vector | collection/index/schema discovery + bounded vector/hybrid search | #767 |
| Property graph / RDF | label/type/relationship/property + bounded traversal/query template | #768 |
| Document / search / key-value / time-series | native collection/index/mapping discovery | #769 |
| DB 전 계열 세부 권한 | column/row/collection/graph scope | #770 |

대상 벤더에는 PostgreSQL/pgvector, MySQL/MariaDB, SQL Server, Oracle, Snowflake, BigQuery,
Redshift, Databricks SQL, Pinecone, Milvus, Qdrant, Weaviate, Chroma, Redis, Neo4j, Neptune,
ArangoDB, MongoDB, Elasticsearch/OpenSearch, DynamoDB, Cosmos DB, Couchbase, ClickHouse,
호환 SPARQL 시스템 등이 포함됩니다.

벤더별 credential과 client object는 SchemaRouter의 model-visible graph에 넣지 않고
adapter/plugin 뒤의 trusted runtime state로 유지합니다.

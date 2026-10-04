# Enterprise data onboarding

SchemaRouter can register internal data systems as typed, bounded capabilities while the host
application remains responsible for identity, credentials, network access, and native database
permissions.

The enterprise boundary is:

```text
verified principal + caller-owned data client
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

SchemaRouter does not authenticate users, store database credentials, or become a general query
proxy.

## Supported data families

| Family | Core onboarding path | Native coverage |
| --- | --- | --- |
| Relational / warehouse | SQLite or caller-owned SQLAlchemy Engine | SQLite plus SQLAlchemy dialect ecosystem |
| Vector | provider-neutral vector contract | Qdrant, Milvus, Pinecone, Weaviate, Chroma, PostgreSQL/pgvector |
| Graph / RDF | provider-neutral graph contract | Neo4j, Neptune, ArangoDB, FalkorDB, SPARQL |
| Document / search / KV / time-series | provider-neutral record contract | MongoDB, Elasticsearch/OpenSearch, DynamoDB, Cosmos DB, Couchbase, ClickHouse, InfluxDB |

Generic Redis record/vector/search support is not part of the first-class core surface. FalkorDB is
supported specifically as a graph database through the graph capability contract.

Vendor clients and connection pools stay caller-owned. SchemaRouter registers only the bounded
schema and execution surface needed by the agent/application.

## Schema discovery

Relational onboarding reflects tables, views, columns, and primary keys. Other families use their
native schema concepts:

- vector collections/indexes, dimensions, metrics, and metadata fields;
- graph labels/classes, relationship/predicate types, properties, and traversal limits;
- document/search mappings, key fields, filterable fields, text/time capabilities.

Discovery does not imply execution authority. The resulting capability still passes authorization,
binding, argument, and output validation before execution.

## Identity and access scope

The host application supplies a verified `PrincipalContext`. SchemaRouter can then combine RBAC
and ABAC rules for roles, departments, teams, and trusted attributes.

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

Unauthorized capabilities are removed before model-visible retrieval and checked again at execution.
A trusted filter derived from the principal cannot be removed or widened by model arguments.

## Scope by data family

| Family | Principal-aware scope |
| --- | --- |
| Relational | table visibility, visible columns, trusted equality/IN row filters |
| Vector | collection visibility, result fields, trusted metadata filters |
| Document/search/KV/time-series | source visibility, projected fields, trusted exact-match filters |
| Graph/RDF | graph visibility, projected fields, allowed relationships/predicates, maximum hops |

Database-native roles, grants, RLS, ACLs, tenant credentials, and network controls remain the final
authority. SchemaRouter may narrow those rights but never broaden them.

## Read-only execution boundary

The core enterprise data adapters deliberately expose bounded operations instead of arbitrary vendor
query languages.

Relational adapters do not accept model-generated SQL. Vector adapters do not expose raw query
objects. Record adapters do not expose Mongo/Elasticsearch/Dynamo/Cosmos/Flux command languages.
Graph adapters do not expose arbitrary Cypher/AQL/Gremlin/SPARQL text.

This keeps schema discovery separate from query authority.

## Choose the onboarding guide

- [Relational database onboarding](database-onboarding.md)
- [Vector store onboarding](vector-store-onboarding.md)
- [Graph and RDF onboarding](graph-store-onboarding.md)
- [NoSQL record-store onboarding](record-store-onboarding.md)
- [Principal-aware authorization](authorization.md)

For provider/API systems rather than databases, see
[provider-first registration](provider-first-registration.md).

# Vector store 등록

SchemaRouter는 vendor client, credential, raw vector, embedding model을 model-visible contract에
넣지 않고 vector collection/index를 typed bounded search capability로 노출할 수 있습니다.

## Provider-neutral contract

Trusted backend가 collection discovery와 search를 구현하고, host가 query embedder를 제공합니다.

```python
keys = router.add_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

Async SDK라면 다음을 사용합니다.

```python
keys = await router.aadd_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

Collection discovery가 선언하는 항목은 다음과 같습니다.

- collection/index 이름
- vector dimension
- distance/similarity metric
- model-visible metadata field
- 명시적으로 공개할 collection metadata

SchemaRouter는 이를 collection별 typed `search` capability로 컴파일합니다.

## 보안 경계

모델은 자연어 `query`와 bounded `top_k`만 전달합니다. 실제 vector는 trusted host embedder가
실행 시점에 만듭니다. Vector-store client와 embedding model은 ToolSpec 밖에 남습니다.

Adapter는 backend 호출 전에 embedding dimension이 introspect한 collection contract와 맞는지
검증합니다.

모델이 임의의 vendor query object나 raw backend command를 실행할 수 있는 API는 없습니다.

## 권한관리

각 collection이 별도 capability가 되므로 principal-aware authorization을 그대로 적용할 수
있습니다.

```python
AuthorizationRule(
    effect="allow",
    operation="vectors.public_docs.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="vectors.executive_memos.*",
    roles_any=("executive",),
)
```

권한이 없는 collection은 model selection 이전에 숨기고 실행 직전에 다시 검증합니다.

Principal DataScope 규칙에서 나온 metadata/tenant filter는 execution 시 trusted filter로
적용합니다. Vendor adapter는 모델 argument가 trusted tenant/department filter를 덮어쓰게
해서는 안 됩니다.

## Vendor adapter

Core contract는 Pinecone, Milvus, Qdrant, Weaviate, Chroma, pgvector가 SchemaRouter의 execution-authority model을 바꾸지 않고 thin adapter로 붙을 수 있도록 vendor-neutral하게 설계했습니다. Redis 계열 vector/search 지원은 first-class core가 아니라 plugin 또는 adopter-specific adapter 범위로 둡니다.

다만 provider-neutral contract와 native adapter가 존재한다는 사실이 모든 vendor/deployment의
live acceptance가 끝났다는 뜻은 아닙니다. SDK-shape/contract 검증은 release gate에 포함하고
외부 live acceptance는 deployment별로 구분합니다.

## Native vendor client

Qdrant와 Milvus는 caller-owned client를 감싸는 thin adapter를 제공합니다. Connection URL,
API key, token, client pool은 해당 client object 내부에 남고 SchemaRouter의 ToolSpec으로
복사되지 않습니다.

### Qdrant

```python
from qdrant_client import QdrantClient

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

keys = router.add_qdrant_vector_store(
    client,
    embed_query,
    database_name="qdrant",
)
```

Adapter가 collection의 vector size/distance와 indexed payload schema를 읽고
`query_points()` 결과를 공통 vector capability contract로 정규화합니다. Dense named vector가
여러 개라면 추측하지 않고 `vector_name_by_collection`으로 명시해야 합니다.

Qdrant payload schema는 indexed/filterable payload field를 나타내며 모든 point에 저장된 모든
payload field를 완전히 기술하지 않을 수 있습니다. 추가 model-visible metadata는
`metadata_fields_by_collection`으로 명시할 수 있습니다.

Trusted data-scope filter는 adapter 내부에서 Qdrant Filter로 변환합니다. 별도의 trusted
filter abstraction이 필요한 application은 `filter_builder`를 주입할 수 있습니다.

### Milvus

```python
from pymilvus import MilvusClient

client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)

keys = router.add_milvus_vector_store(
    client,
    embed_query,
    database_name="milvus",
)
```

Adapter는 `list_collections()`와 `describe_collection()`으로 dense vector dimension과
scalar metadata field를 파악합니다. Vector field가 여러 개라면
`vector_field_by_collection`으로 명시합니다.

Trusted filter는 Milvus filter template과 `filter_params`를 사용하므로 principal-derived
값을 expression 문자열에 직접 삽입하지 않습니다.

이 adapter들은 caller-owned fake client로 SDK-shape contract를 검증합니다. Vendor credential은
SchemaRouter state에 들어가지 않으며, 모든 deployment topology의 live acceptance가 끝났다는
의미는 아닙니다.

### Pinecone

```python
keys = router.add_pinecone_vector_store(
    pinecone_client,
    embed_query,
    database_name="pinecone",
)
```

Caller-owned Pinecone client에서 index 이름, dimension, metric을 읽습니다. Pinecone은 완전한
metadata schema를 제공하지 않으므로 필요한 model-visible metadata는
`metadata_fields_by_index`로 보완할 수 있습니다.

### Weaviate

```python
keys = router.add_weaviate_vector_store(
    weaviate_client,
    embed_query,
    dimension_by_collection={"Article": 1536},
)
```

v4 collection API에서 property를 발견합니다. 모든 구성에서 vector dimension을 안정적으로
얻을 수 있는 것은 아니므로 dimension은 명시할 수 있게 하고, named vector는
`vector_name_by_collection`으로 선택합니다.

### Chroma

```python
keys = router.add_chroma_vector_store(
    chroma_client,
    embed_query,
)
```

기존 embedding이 있는 collection은 dimension을 자동 추론합니다. 비어 있는 collection은
`dimension_by_collection`을 명시해야 하며 metadata schema가 불완전하면 field를 명시적으로
보완할 수 있습니다.

### PostgreSQL / pgvector

```python
keys = router.add_pgvector_store(
    sqlalchemy_engine,
    embed_query,
    tables=["document_embeddings"],
)
```

Caller-owned SQLAlchemy/pgvector runtime에서 VECTOR column과 primary key를 reflection하고,
SQLAlchemy expression으로 bounded distance ordering과 trusted metadata filter를 적용합니다.
VECTOR column이 여러 개면 `vector_field_by_table`로 명시합니다.

현재 native adapter surface는 Qdrant, Milvus, Pinecone, Weaviate, Chroma, PostgreSQL/pgvector를 포함합니다. 이는 SDK-shape/contract 검증 범위이며 모든 hosted
deployment의 live acceptance가 끝났다는 뜻은 아닙니다.


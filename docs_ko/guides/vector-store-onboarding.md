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

Metadata/tenant filter 강제는 #770의 cross-family data-scope 단계에서 추가합니다. Vendor
adapter는 모델 argument가 trusted tenant/department filter를 덮어쓰게 해서는 안 됩니다.

## Vendor adapter

Core contract는 Pinecone, Milvus, Qdrant, Weaviate, Chroma, Redis vector/search, pgvector가
SchemaRouter의 execution-authority model을 바꾸지 않고 thin adapter로 붙을 수 있도록
vendor-neutral하게 설계했습니다.

다만 provider-neutral contract 구현만으로 위 모든 vendor SDK의 native/live acceptance가
끝났다는 뜻은 아닙니다. Vendor별 adapter acceptance는 #767에서 계속 추적합니다.

## Native Qdrant / Milvus client

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
    metadata_fields_by_index={"docs": metadata_fields},
)
```

Pinecone control plane에서 index dimension과 metric을 읽습니다. Pinecone이 index의 전체
metadata schema를 제공하지 않으므로 projection이나 trusted principal filter에 사용할
metadata field는 명시적으로 선언합니다.

### Weaviate

```python
keys = router.add_weaviate_vector_store(
    weaviate_client,
    embed_query,
    dimension_by_collection={"Docs": 1536},
)
```

Collection/property는 자동 탐색하고 vector dimension은 명시적으로 제공합니다. Weaviate
schema metadata에서 dimension을 일관되게 얻기 어렵기 때문입니다. Trusted authorization
filter는 adapter 내부 또는 caller-supplied `filter_builder`에서 컴파일합니다.

### Chroma

```python
keys = router.add_chroma_vector_store(
    chroma_client,
    embed_query,
    dimension_by_collection={"docs": 1536},
)
```

Collection을 탐색하고 bounded `peek(limit=1)`로 metadata key를 추론할 수 있습니다.
Dimension은 명시하거나 trusted collection metadata에서 읽습니다.

### pgvector / PostgreSQL

```python
keys = router.add_pgvector_store(
    sqlalchemy_engine,
    embed_query,
    tables=["documents"],
    metric_by_table={"documents": "cosine"},
)
```

Caller-selected SQLAlchemy table을 reflection하여 dense vector column과 dimension을
파악하고 SQLAlchemy expression으로 similarity search를 구성합니다. 모델에는 SQL text나
raw vector를 노출하지 않습니다. PostgreSQL role/RLS가 최종 권한 경계로 유지됩니다.

모든 native vector adapter의 credential과 connection object는 caller-owned 상태로
유지됩니다. SDK-shape test는 discovery, bounded top-k search, metadata projection,
trusted-filter 처리를 검증하며 live acceptance는 deployment 환경의 실제 credential에
의존합니다.

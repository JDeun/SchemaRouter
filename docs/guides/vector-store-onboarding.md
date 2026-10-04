# Vector store onboarding

SchemaRouter can expose vector collections/indexes as typed, bounded search capabilities without
placing vendor clients, credentials, raw vectors, or embedding models in model-visible contracts.

## Provider-neutral contract

A trusted backend implements collection discovery and search, while the host supplies the query
embedder:

```python
keys = router.add_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

For async SDKs, use:

```python
keys = await router.aadd_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

Collection discovery declares:

- collection/index name;
- vector dimension;
- distance/similarity metric;
- model-visible metadata fields;
- explicitly public collection metadata.

SchemaRouter compiles those declarations into one typed `search` capability per collection.

## Security boundary

The model receives a natural-language `query` and bounded `top_k`. The trusted host embedder
creates the vector at execution time. The vector-store client and embedding model stay outside
ToolSpec.

The adapter validates the returned embedding dimension against the introspected collection
contract before calling the backend.

There is no model-visible API for arbitrary vendor query objects or raw backend commands.

## Authorization

Each collection becomes its own capability, so the same principal-aware authorization policy can
hide or expose collections before retrieval:

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

Unauthorized collections are non-disclosed before model selection and revalidated before
execution.

Metadata/tenant filter enforcement is the next cross-family data-scope layer in #770. A vendor
adapter must not allow model arguments to override trusted tenant or department filters.

## Vendor adapters

The core contract is vendor-neutral so Pinecone, Milvus, Qdrant, Weaviate, Chroma, Redis
vector/search and pgvector can implement thin adapters without changing SchemaRouter's execution
authority model.

The provider-neutral contract does **not** by itself claim that every named vendor SDK has completed
native/live acceptance. Vendor-specific adapter acceptance is tracked under #767.

## Native Qdrant and Milvus clients

For Qdrant and Milvus, SchemaRouter ships thin adapters around caller-owned clients. Connection
URLs, API keys, tokens, and client pools remain inside those client objects.

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

The adapter reads collection vector size/distance and indexed payload schema, then normalizes
`query_points()` results into the common vector capability contract. When a collection has
multiple named dense vectors, set `vector_name_by_collection` explicitly rather than guessing.

Qdrant payload schema describes indexed/filterable payload fields, not necessarily every payload
field stored in every point. Additional model-visible metadata may therefore be supplied explicitly
with `metadata_fields_by_collection`.

Trusted data-scope filters are converted to Qdrant Filter objects inside the adapter. Applications
with a custom Qdrant filter abstraction may inject a trusted `filter_builder`.

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

The adapter uses `list_collections()` and `describe_collection()` to discover dense vector
dimensions and scalar metadata fields. If a collection has multiple vector fields, use
`vector_field_by_collection` explicitly.

Trusted filters use Milvus filter templates plus `filter_params`; principal-derived values are not
interpolated into the expression string.

These adapters are SDK-shape tested with caller-owned fake clients. They do not make vendor
credentials part of SchemaRouter state and do not imply that every deployment topology has been
live-tested.



### Pinecone

```python
keys = router.add_pinecone_vector_store(
    pinecone_client,
    embed_query,
    metadata_fields_by_index={"docs": metadata_fields},
)
```

Index dimension and metric are read from the Pinecone control plane. Metadata fields that may be
projected or used for trusted principal filters are declared explicitly because Pinecone does not
provide a complete metadata schema for an index.

### Weaviate

```python
keys = router.add_weaviate_vector_store(
    weaviate_client,
    embed_query,
    dimension_by_collection={"Docs": 1536},
)
```

Weaviate collection/property discovery is automatic. Vector dimensions are supplied explicitly
because they are not consistently exposed through collection schema metadata. Trusted authorization
filters are compiled inside the adapter or by a caller-supplied `filter_builder`.

### Chroma

```python
keys = router.add_chroma_vector_store(
    chroma_client,
    embed_query,
    dimension_by_collection={"docs": 1536},
)
```

The adapter discovers collections and can infer metadata keys from a bounded `peek(limit=1)`.
Dimensions may be provided explicitly or through trusted collection metadata.

### pgvector / PostgreSQL

```python
keys = router.add_pgvector_store(
    sqlalchemy_engine,
    embed_query,
    tables=["documents"],
    metric_by_table={"documents": "cosine"},
)
```

The pgvector adapter reflects caller-selected SQLAlchemy tables, discovers a single dense vector
column and its dimension, and builds similarity search using SQLAlchemy expressions. The model never
receives SQL text or a vector value. Native PostgreSQL roles/RLS remain authoritative.

All native vector adapters keep credentials and connection objects caller-owned. SDK-shape tests
cover discovery, bounded top-k search, metadata projection, and trusted-filter handling. Live
acceptance remains environment-dependent and should use deployment-owned credentials.

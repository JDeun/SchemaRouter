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

Metadata/tenant filters from principal DataScope rules are applied as trusted filters at execution.
A vendor adapter must not allow model arguments to override those tenant or department filters.

## Vendor adapters

The core contract is vendor-neutral so Pinecone, Milvus, Qdrant, Weaviate, Chroma, and pgvector can implement thin adapters without changing SchemaRouter's execution authority model. Redis-specific vector/search support is intentionally left to plugins or adopter-specific adapters rather than the first-class core surface.

The provider-neutral contract does **not** by itself claim that every named vendor SDK has completed
live acceptance. Native adapter contracts and SDK-shape coverage are release-gated; live external
acceptance remains deployment-specific.

## Native vendor clients

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
    database_name="pinecone",
)
```

The adapter discovers index names, dimension and metric through the caller-owned Pinecone client.
Pinecone does not expose a complete metadata schema, so model-visible metadata fields may be
declared with `metadata_fields_by_index`. Trusted DataScope filters are passed through Pinecone's
structured `filter` argument rather than interpolated query text.

### Weaviate

```python
keys = router.add_weaviate_vector_store(
    weaviate_client,
    embed_query,
    dimension_by_collection={"Article": 1536},
)
```

Weaviate collection properties are discovered through the v4 collections API. Vector dimension is
explicit because it is not reliably available from every collection configuration. Named vectors
can be selected with `vector_name_by_collection`.

### Chroma

```python
keys = router.add_chroma_vector_store(
    chroma_client,
    embed_query,
)
```

The adapter discovers collections and can infer vector dimension from an existing embedding. Empty
collections require `dimension_by_collection`. Metadata fields can be declared explicitly when the
collection does not expose a stable schema.

### PostgreSQL / pgvector

```python
keys = router.add_pgvector_store(
    sqlalchemy_engine,
    embed_query,
    tables=["document_embeddings"],
)
```

The adapter reflects VECTOR columns and primary keys through caller-owned SQLAlchemy/pgvector
runtime state, then uses SQLAlchemy expressions for bounded distance ordering and trusted metadata
filters. If a table has multiple VECTOR columns, select one explicitly with
`vector_field_by_table`.

The native adapter surface now covers Qdrant, Milvus, Pinecone, Weaviate, Chroma, and PostgreSQL/pgvector. These are SDK-shape and contract tests, not a claim that every
deployment topology or hosted account has been live-tested.


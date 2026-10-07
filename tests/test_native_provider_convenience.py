from __future__ import annotations

from pathlib import Path

from schemarouter.native_provider_convenience import NativeProviderConvenienceMixin
from schemarouter.runtime import SchemaRouter

ROOT = Path(__file__).resolve().parents[1]


def test_named_native_provider_convenience_api_is_inherited_from_mixin() -> None:
    expected = {
        "aadd_qdrant_vector_store",
        "add_qdrant_vector_store",
        "aadd_milvus_vector_store",
        "add_milvus_vector_store",
        "aadd_pinecone_vector_store",
        "add_pinecone_vector_store",
        "aadd_chroma_vector_store",
        "add_chroma_vector_store",
        "aadd_weaviate_vector_store",
        "add_weaviate_vector_store",
        "aadd_pgvector_store",
        "add_pgvector_store",
        "aadd_neo4j_graph",
        "add_neo4j_graph",
        "aadd_falkordb_graph",
        "add_falkordb_graph",
        "aadd_neptune_graph",
        "add_neptune_graph",
        "aadd_arango_graph",
        "add_arango_graph",
        "aadd_sparql_graph",
        "add_sparql_graph",
        "aadd_mongodb_record_store",
        "add_mongodb_record_store",
        "aadd_elasticsearch_record_store",
        "add_elasticsearch_record_store",
        "aadd_opensearch_record_store",
        "add_opensearch_record_store",
        "aadd_dynamodb_record_store",
        "add_dynamodb_record_store",
        "aadd_cosmos_record_store",
        "add_cosmos_record_store",
        "aadd_couchbase_record_store",
        "add_couchbase_record_store",
        "aadd_clickhouse_record_store",
        "add_clickhouse_record_store",
        "aadd_influxdb_record_store",
        "add_influxdb_record_store",
    }

    assert issubclass(SchemaRouter, NativeProviderConvenienceMixin)
    assert expected <= set(dir(SchemaRouter))


def test_runtime_facade_no_longer_owns_named_provider_method_bodies() -> None:
    runtime = (ROOT / "src" / "schemarouter" / "runtime.py").read_text(
        encoding="utf-8"
    )

    for representative in (
        "aadd_qdrant_vector_store",
        "aadd_neo4j_graph",
        "aadd_mongodb_record_store",
    ):
        assert f"def {representative}(" not in runtime

    mixin = (
        ROOT / "src" / "schemarouter" / "native_provider_convenience.py"
    ).read_text(encoding="utf-8")
    for representative in (
        "aadd_qdrant_vector_store",
        "aadd_neo4j_graph",
        "aadd_mongodb_record_store",
    ):
        assert f"def {representative}(" in mixin

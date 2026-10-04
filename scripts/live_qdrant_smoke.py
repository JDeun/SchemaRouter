from __future__ import annotations

import argparse
import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from schemarouter.adapters.vector_native import QdrantVectorBackend
from schemarouter.adapters.vector_store import VectorMetadataField


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:6333")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    client = QdrantClient(url=args.url)
    collection = "schemarouter_live"
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=3, distance=Distance.COSINE),
    )
    client.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=1,
                vector=[1.0, 0.0, 0.0],
                payload={"title": "tenant-a doc", "tenant": "tenant-a", "secret": "hidden"},
            ),
            PointStruct(
                id=2,
                vector=[0.9, 0.1, 0.0],
                payload={"title": "tenant-b doc", "tenant": "tenant-b", "secret": "hidden"},
            ),
        ],
        wait=True,
    )

    backend = QdrantVectorBackend(
        client,
        metadata_fields_by_collection={
            collection: (
                VectorMetadataField(name="title", json_schema={"type": "string"}),
                VectorMetadataField(
                    name="tenant",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
            )
        },
    )
    specs = backend.list_collections()
    spec = next(item for item in specs if item.name == collection)
    rows = backend.search(
        collection=collection,
        vector=[1.0, 0.0, 0.0],
        top_k=5,
        include_fields=("title",),
        filters={"tenant": "tenant-a"},
    )
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert len(rows) == 1
    assert rows[0]["title"] == "tenant-a doc"
    assert "tenant" not in rows[0]
    assert "secret" not in rows[0]

    report = {
        "adapter": "qdrant",
        "service": "qdrant/qdrant",
        "discovery": "success",
        "bounded_search": "success",
        "field_projection": "success",
        "trusted_filter": "success",
        "raw_query_surface": False,
    }
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

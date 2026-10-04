from __future__ import annotations

import argparse
import json
from pathlib import Path

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from schemarouter.adapters.vector_native import PgvectorVectorBackend


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    engine = create_engine(args.url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")

    metadata = MetaData()
    documents = Table(
        "schemarouter_live_vectors",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("embedding", VECTOR(3), nullable=False),
        Column("title", String, nullable=False),
        Column("tenant", String, nullable=False),
        Column("secret", String, nullable=False),
    )
    metadata.drop_all(engine, checkfirst=True)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(documents),
            [
                {
                    "id": 1,
                    "embedding": [1.0, 0.0, 0.0],
                    "title": "tenant-a doc",
                    "tenant": "tenant-a",
                    "secret": "hidden-a",
                },
                {
                    "id": 2,
                    "embedding": [0.9, 0.1, 0.0],
                    "title": "tenant-b doc",
                    "tenant": "tenant-b",
                    "secret": "hidden-b",
                },
            ],
        )

    backend = PgvectorVectorBackend(
        engine,
        tables=(documents.name,),
        metric_by_table={documents.name: "cosine"},
    )
    specs = backend.list_collections()
    spec = next(item for item in specs if item.name == documents.name)
    rows = backend.search(
        collection=documents.name,
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
        "adapter": "pgvector",
        "service": "pgvector/pgvector:pg16",
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

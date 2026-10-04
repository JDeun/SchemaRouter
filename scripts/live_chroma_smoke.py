from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

import chromadb

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
    TrustedFilterBinding,
)
from schemarouter.adapters.vector_store import VectorMetadataField


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    client = chromadb.Client()
    collection_name = "schemarouter_live"
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=["1", "2"],
        embeddings=[
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
        ],
        metadatas=[
            {"title": "tenant-a doc", "tenant": "tenant-a", "secret": "hidden-a"},
            {"title": "tenant-b doc", "tenant": "tenant-b", "secret": "hidden-b"},
        ],
        documents=["visible a", "visible b"],
    )

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employee-search",
                effect="allow",
                operation="chroma_live.*.search",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                name="tenant-scope",
                operation="chroma_live.*.search",
                roles_any=("employee",),
                visible_fields=("id", "score", "title"),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant",
                    ),
                ),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    keys = router.add_chroma_vector_store(
        client,
        lambda query: [1.0, 0.0, 0.0],
        database_name="chroma_live",
        collections={collection_name},
        dimension_by_collection={collection_name: 3},
        metadata_fields_by_collection={
            collection_name: (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
                VectorMetadataField(
                    name="tenant",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
            )
        },
        metric_by_collection={collection_name: "cosine"},
        remote=False,
    )
    tool = router.registry.get(keys[0])
    endpoint = tool.endpoint("search")
    assert endpoint.execution_metadata["dimension"] == 3
    assert endpoint.execution_metadata["metric"] == "cosine"
    assert endpoint.read_only is True
    assert {field.name for field in endpoint.output_fields} == {
        "id",
        "score",
        "title",
        "tenant",
    }

    principal = PrincipalContext(
        subject="employee-1",
        roles=("employee",),
        attributes={"tenant": "tenant-a"},
    )
    retrieval = router.retrieve_authorized(
        "tenant document title",
        principal=principal,
        k=5,
    )
    candidate = next(item for item in retrieval.candidates if item.tool == tool.key)
    assert {field.name for field in candidate.output_fields} == {"id", "score", "title"}
    assert "tenant" not in {field.name for field in candidate.output_fields}

    plan = ExecutionPlan(
        query="find my tenant document",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"query": "tenant document", "top_k": 5},
                fields=["title"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )
    result = asyncio.run(
        router.execute(
            plan,
            config=RunConfig(principal=principal),
        )
    )[0].data
    assert len(result) == 1
    assert result[0] == {"title": "tenant-a doc"}

    report = {
        "adapter": "chroma",
        "service": "in-process",
        "client": f"chromadb=={version('chromadb')}",
        "discovery": "success",
        "bounded_search": "success",
        "field_projection": "success",
        "trusted_filter": "success",
        "principal_schema_projection": "success",
        "raw_query_surface": False,
    }
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

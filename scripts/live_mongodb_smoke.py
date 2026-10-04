from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

from pymongo import MongoClient

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="mongodb://127.0.0.1:27017")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=3_000)
    client.admin.command("ping")
    database = client["schemarouter_live"]
    collection = database["documents"]
    collection.drop()
    collection.insert_many(
        [
            {
                "title": "tenant-a doc",
                "tenant": "tenant-a",
                "secret": "hidden-a",
            },
            {
                "title": "tenant-b doc",
                "tenant": "tenant-b",
                "secret": "hidden-b",
            },
        ]
    )

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employee-read",
                effect="allow",
                operation="mongodb_live.*.query",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                name="tenant-scope",
                operation="mongodb_live.*.query",
                roles_any=("employee",),
                visible_fields=("title",),
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
    keys = router.add_mongodb_record_store(
        database,
        database_name="mongodb_live",
        collections=(collection.name,),
        remote=False,
    )
    tool = router.registry.get(keys[0])
    endpoint = tool.endpoint("query")
    declared = {field.name for field in endpoint.output_fields}
    assert {"_id", "title", "tenant", "secret"}.issubset(declared)
    assert endpoint.read_only is True
    assert all(parameter.name != "raw_query" for parameter in endpoint.parameters)

    principal = PrincipalContext(
        subject="employee-1",
        roles=("employee",),
        attributes={"tenant": "tenant-a"},
    )
    retrieval = router.retrieve_authorized(
        "document title",
        principal=principal,
        k=5,
    )
    candidate = next(item for item in retrieval.candidates if item.tool == tool.key)
    assert [field.name for field in candidate.output_fields] == ["title"]
    assert "filter__tenant" not in {parameter.name for parameter in candidate.parameters}

    plan = ExecutionPlan(
        query="read my tenant document title",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"limit": 5},
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
    assert result == [{"title": "tenant-a doc"}]

    report = {
        "adapter": "mongodb",
        "service": "mongo:8.0.32-noble",
        "client": f"pymongo=={version('pymongo')}",
        "discovery": "success",
        "bounded_read": "success",
        "field_projection": "success",
        "trusted_filter": "success",
        "principal_schema_projection": "success",
        "raw_query_surface": False,
    }
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

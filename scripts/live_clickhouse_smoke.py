from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

import clickhouse_connect

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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--username", default="default")
    parser.add_argument("--password", default="schemarouter")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    client = clickhouse_connect.get_client(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
    )
    source = "default.schemarouter_live"
    client.command(f"DROP TABLE IF EXISTS {source}")
    client.command(
        f"""
        CREATE TABLE {source} (
            id UInt32,
            title String,
            tenant String,
            secret String,
            ts DateTime
        )
        ENGINE = MergeTree
        ORDER BY id
        """
    )
    client.command(
        f"""
        INSERT INTO {source} VALUES
          (1, 'tenant-a doc', 'tenant-a', 'hidden-a', toDateTime('2026-10-04 00:00:00')),
          (2, 'tenant-b doc', 'tenant-b', 'hidden-b', toDateTime('2026-10-04 01:00:00'))
        """
    )

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employee-read",
                effect="allow",
                operation="clickhouse_live.*.query",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                name="tenant-scope",
                operation="clickhouse_live.*.query",
                roles_any=("employee",),
                visible_fields=("title", "ts"),
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
    keys = router.add_clickhouse_record_store(
        client,
        database_name="clickhouse_live",
        tables=(source,),
        time_field_by_table={source: "ts"},
        remote=False,
    )
    tool = router.registry.get(keys[0])
    endpoint = tool.endpoint("query")
    assert endpoint.metadata["record_model"] == "time_series"
    assert endpoint.metadata["time_field"] == "ts"
    assert endpoint.read_only is True
    assert "raw_query" not in {parameter.name for parameter in endpoint.parameters}

    principal = PrincipalContext(
        subject="employee-1",
        roles=("employee",),
        attributes={"tenant": "tenant-a"},
    )
    retrieval = router.retrieve_authorized(
        "time series document title",
        principal=principal,
        k=5,
    )
    candidate = next(item for item in retrieval.candidates if item.tool == tool.key)
    assert {field.name for field in candidate.output_fields} == {"title", "ts"}
    assert "filter__tenant" not in {parameter.name for parameter in candidate.parameters}

    plan = ExecutionPlan(
        query="read my tenant events",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={
                    "start_time": "2026-10-04 00:00:00",
                    "end_time": "2026-10-05 00:00:00",
                    "limit": 5,
                },
                fields=["title", "ts"],
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
    assert result[0]["title"] == "tenant-a doc"
    assert "tenant" not in result[0]
    assert "secret" not in result[0]

    report = {
        "adapter": "clickhouse",
        "service": "clickhouse/clickhouse-server:26.8.11.7",
        "client": f"clickhouse-connect=={version('clickhouse-connect')}",
        "discovery": "success",
        "bounded_read": "success",
        "time_bounds": "success",
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

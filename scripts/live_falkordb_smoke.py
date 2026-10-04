from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from falkordb import FalkorDB

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall


def _connect_with_retry(host: str, port: int, timeout_seconds: float = 30.0) -> FalkorDB:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client = FalkorDB(host=host, port=port)
            client.list_graphs()
            return client
        except Exception as exc:  # pragma: no cover - live compatibility retry
            last_error = exc
            time.sleep(1.0)
    raise RuntimeError("FalkorDB did not become ready") from last_error


def run(host: str, port: int) -> dict[str, Any]:
    client = _connect_with_retry(host, port)
    graph_name = "schemarouter_acceptance"
    graph = client.select_graph(graph_name)

    try:
        graph.delete()
    except Exception:
        pass

    graph.query(
        "CREATE "
        "(p:Person {name: 'Alice', department: 'engineering'}), "
        "(t:Team {name: 'Platform'}), "
        "(p)-[:MEMBER_OF {since: 2026}]->(t)"
    )
    start_id = str(
        graph.ro_query(
            "MATCH (p:Person {name: 'Alice'}) RETURN id(p)"
        ).result_set[0][0]
    )

    router = SchemaRouter()
    keys = router.add_falkordb_graph(
        client,
        graphs={graph_name},
        remote=False,
    )
    tool = router.registry.get(keys[0])
    endpoint = tool.endpoint("traverse")
    plan = ExecutionPlan(
        query="Which team is Alice a member of?",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={
                    "start_id": start_id,
                    "relationship_types": ["MEMBER_OF"],
                    "direction": "out",
                    "max_hops": 1,
                    "limit": 5,
                },
                fields=[
                    "source_id",
                    "target_id",
                    "relationship",
                    "depth",
                    "source_type",
                    "target_type",
                ],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )
    result = asyncio.run(router.execute(plan))[0].data
    if not result or result[0].get("relationship") != "MEMBER_OF":
        raise RuntimeError(f"unexpected FalkorDB traversal result: {result!r}")

    node_types = endpoint.metadata["node_types"]
    relationships = endpoint.metadata["relationship_types"]
    return {
        "status": "ok",
        "registered_keys": list(keys),
        "start_id": start_id,
        "result": result,
        "node_types": node_types,
        "relationship_types": relationships,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    payload = run(args.host, args.port)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

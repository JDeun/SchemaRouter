from __future__ import annotations

import argparse
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import (
    ExecutionPlan,
    ProviderAccessMethod,
    ProviderProfile,
    SchemaRouter,
    ToolCall,
)


def _type_ref(kind: str, name: str | None = None, of_type: dict | None = None) -> dict:
    return {"kind": kind, "name": name, "ofType": of_type}


def _introspection() -> dict:
    item_type = {
        "kind": "OBJECT",
        "name": "ReferenceItem",
        "description": None,
        "fields": [
            {
                "name": "id",
                "description": "Reference identifier",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _type_ref("NON_NULL", of_type=_type_ref("SCALAR", "ID")),
            },
            {
                "name": "name",
                "description": "Reference name",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [],
                "type": _type_ref("SCALAR", "String"),
            },
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    query_type = {
        "kind": "OBJECT",
        "name": "Query",
        "description": None,
        "fields": [
            {
                "name": "item",
                "description": "Get one reference item.",
                "isDeprecated": False,
                "deprecationReason": None,
                "args": [
                    {
                        "name": "id",
                        "description": "Reference id",
                        "defaultValue": None,
                        "type": _type_ref(
                            "NON_NULL",
                            of_type=_type_ref("SCALAR", "ID"),
                        ),
                    }
                ],
                "type": _type_ref("OBJECT", "ReferenceItem"),
            }
        ],
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    scalar = lambda name: {
        "kind": "SCALAR",
        "name": name,
        "description": None,
        "fields": None,
        "inputFields": None,
        "enumValues": None,
        "possibleTypes": None,
    }
    return {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "mutationType": None,
                "subscriptionType": None,
                "types": [
                    query_type,
                    item_type,
                    scalar("ID"),
                    scalar("String"),
                ],
            }
        }
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "SchemaRouterGraphQLReference/1"

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send_json(self, payload: object) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/graphql":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        query = str(payload.get("query", ""))
        if "__schema" in query:
            self._send_json(_introspection())
            return
        self._send_json(
            {
                "data": {
                    "item": {
                        "id": "1",
                        "name": "SchemaRouter reference",
                    }
                }
            }
        )


async def run_smoke() -> dict[str, object]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    source = f"http://127.0.0.1:{port}/graphql"
    router: SchemaRouter | None = None

    try:
        router = SchemaRouter()
        router.register_provider_profile(
            ProviderProfile(
                provider_id="local-graphql-reference",
                display_name="SchemaRouter local GraphQL reference",
                methods=(
                    ProviderAccessMethod(
                        method_id="graphql",
                        kind="graphql",
                        access_mode="graphql",
                        url=source,
                    ),
                ),
            )
        )

        started = perf_counter()
        registration = await router.add_provider("local-graphql-reference")
        discovery_ms = round((perf_counter() - started) * 1000, 2)
        assert registration.methods[0].status == "registered"
        assert len(registration.registered_tool_keys) == 1

        tool = router.registry.get(registration.registered_tool_keys[0])
        assert tool.provider == "local-graphql-reference"
        assert tool.access_mode == "graphql"
        endpoint = tool.endpoint("item")
        available_fields = {field.name for field in endpoint.output_fields}
        assert {"id", "name"} <= available_fields

        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"id": "1"},
            fields=["id", "name"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="reference GraphQL item",
            registry_version=router.registry.version,
            calls=[call],
        )

        started = perf_counter()
        results = await router.execute(plan)
        execution_ms = round((perf_counter() - started) * 1000, 2)

        assert len(results) == 1
        assert results[0].data == {
            "id": "1",
            "name": "SchemaRouter reference",
        }

        return {
            "source": source,
            "evidence_kind": "pinned_reference_implementation",
            "provider": "SchemaRouter local GraphQL reference",
            "provider_first": True,
            "discovery_success": True,
            "tool_count": 1,
            "endpoint_count": len(tool.endpoints),
            "execution_bound": router.executor.is_binding_ready_for_contract(
                tool.key,
                tool.fingerprint,
            ),
            "execution_success": True,
            "safe_endpoint": endpoint.name,
            "returned_shape": "object",
            "selected_fields": ["id", "name"],
            "discovery_latency_ms": discovery_ms,
            "execution_latency_ms": execution_ms,
            "auth_required": endpoint.auth_required,
            "known_quirks": [
                "Pinned local GraphQL reference is used as release-gated provider-first evidence."
            ],
        }
    finally:
        if router is not None:
            await router.aclose()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    report = new_report(
        adapter="provider-profile:graphql-reference:graphql",
        source="pinned-local-graphql-reference",
    )
    report["details"] = {
        "evidence_kind": "pinned_reference_implementation",
        "provider": "SchemaRouter local GraphQL reference",
        "provider_first": True,
    }

    try:
        report["details"].update(await run_smoke())
        report["status"] = "success"
    except Exception as exc:
        report["status"] = "failure"
        report["error_type"] = type(exc).__name__
        write_report(args.json_out, report)
        raise

    write_report(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())

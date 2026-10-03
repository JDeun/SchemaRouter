from __future__ import annotations

import argparse
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import (\n    ExecutionPlan,\n    ExecutionPolicy,\n    ProviderAccessMethod,\n    ProviderProfile,\n    SchemaRouter,\n    ToolCall,\n)


class _Handler(BaseHTTPRequestHandler):
    server_version = "SchemaRouterOpenRPCReference/1"

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send_json(self, payload: object) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/openrpc.json":
            self.send_error(404)
            return
        port = self.server.server_address[1]
        self._send_json(
            {
                "openrpc": "1.4.0",
                "info": {
                    "title": "SchemaRouter pinned OpenRPC reference",
                    "version": "1.0.0",
                },
                "servers": [
                    {
                        "name": "local",
                        "url": f"http://127.0.0.1:{port}/rpc",
                    }
                ],
                "methods": [
                    {
                        "name": "reference.echo",
                        "paramStructure": "by-name",
                        "params": [
                            {
                                "name": "value",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "result": {
                            "name": "Echo result",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "value": {"type": "string"},
                                },
                                "required": ["value"],
                            },
                        },
                    }
                ],
            }
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/rpc":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self._send_json(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"value": payload["params"]["value"]},
            }
        )


async def run_smoke() -> dict[str, object]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    source = f"http://127.0.0.1:{port}/openrpc.json"
    router: SchemaRouter | None = None

    try:
        router = SchemaRouter(
            policy=ExecutionPolicy(allow_unclassified_remote=True)
        )
        router.register_provider_profile(
            ProviderProfile(
                provider_id="local-openrpc-reference",
                display_name="SchemaRouter local OpenRPC JSON-RPC reference",
                methods=(
                    ProviderAccessMethod(
                        method_id="openrpc",
                        kind="openrpc",
                        access_mode="openrpc",
                        url=source,
                    ),
                ),
            )
        )

        started = perf_counter()
        registration = await router.add_provider("local-openrpc-reference")
        discovery_ms = round((perf_counter() - started) * 1000, 2)
        assert registration.methods[0].status == "registered"
        assert len(registration.registered_tool_keys) == 1

        tool = router.registry.get(registration.registered_tool_keys[0])
        assert tool.provider == "local-openrpc-reference"
        assert tool.access_mode == "openrpc"
        endpoint = tool.endpoint("reference.echo")

        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"value": "schemarouter"},
            fields=["value"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="echo reference value",
            registry_version=router.registry.version,
            calls=[call],
        )

        started = perf_counter()
        results = await router.execute(plan)
        execution_ms = round((perf_counter() - started) * 1000, 2)

        assert results[0].data == {"value": "schemarouter"}

        return {
            "source": source,
            "evidence_kind": "pinned_reference_implementation",
            "provider": "SchemaRouter local OpenRPC JSON-RPC reference",
            "provider_first": True,
            "openrpc_version": "1.4.0",
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
            "discovery_latency_ms": discovery_ms,
            "execution_latency_ms": execution_ms,
            "auth_required": False,
            "known_quirks": [
                "No stable unauthenticated public OpenRPC execution endpoint is assumed."
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
    report = new_report(adapter="openrpc", source="pinned-local-reference")
    report["details"] = {
        "evidence_kind": "pinned_reference_implementation",
        "provider": "SchemaRouter local OpenRPC JSON-RPC reference",
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

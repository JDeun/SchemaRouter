"""Exercise the promoted live quickstart path without public-network dependency."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


def _load_example():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "live_openapi_quickstart.py"
    )
    spec = importlib.util.spec_from_file_location(
        "schemarouter_live_openapi_quickstart",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load live OpenAPI quickstart")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document(base_url: str) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Quickstart provider fixture",
            "version": "1.0.0",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/metrics": {
                "get": {
                    "operationId": "getMetrics",
                    "summary": "API directory metrics",
                    "responses": {
                        "200": {
                            "description": "metrics",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["numAPIs"],
                                        "properties": {
                                            "numAPIs": {
                                                "type": "integer",
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@contextmanager
def _fixture_server(metric_value: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            host = self.headers.get("Host")
            if host is None:
                self.send_error(400)
                return
            base_url = f"http://{host}"
            if self.path == "/openapi.json":
                payload = _document(base_url)
            elif self.path == "/metrics":
                payload = {"numAPIs": metric_value}
            else:
                self.send_error(404)
                return

            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def _run() -> None:
    module = _load_example()

    with _fixture_server(321) as base_url:
        result = await module.run_quickstart(
            f"{base_url}/openapi.json",
        )

    if result.endpoint != "getMetrics":
        raise RuntimeError(f"unexpected quickstart endpoint: {result.endpoint}")
    if result.data.get("numAPIs") != 321:
        raise RuntimeError(f"unexpected quickstart result: {result.data!r}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


def _live_quickstart_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "live_openapi_quickstart.py"
    )
    spec = importlib.util.spec_from_file_location(
        "live_openapi_quickstart",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document(base_url: str) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Public API directory",
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


@pytest.mark.asyncio
async def test_live_openapi_quickstart_path_with_offline_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _live_quickstart_module()

    with _fixture_server(123) as base_url:
        source = f"{base_url}/openapi.json"
        result = await module.run_quickstart(source)

    assert result.endpoint == "getMetrics"
    assert result.data["numAPIs"] == 123
    output = capsys.readouterr().out
    assert "provider: quickstart-openapi" in output
    assert f"source: {source}" in output
    assert "discovered:" in output
    assert "selected:" in output
    assert "current numAPIs: 123" in output

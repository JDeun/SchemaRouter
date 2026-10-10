"""Test real CYT Proxy HTTP forwarding to an isolated localhost fake model.

No external model provider, live MCP tools, user API keys, scored tasks,
Codex CLI launch, or held-out workload. Only loopback HTTP is used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


async def probe() -> dict[str, Any]:
    import httpx
    from cyt.proxy.reverse import create_app

    captured: list[dict[str, Any]] = []

    class LocalModel(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            data = self.rfile.read(length)
            request_body = json.loads(data)
            captured.append({
                "path": self.path,
                "method": self.command,
                "body": request_body,
            })
            response = json.dumps({
                "id": "resp_cyt_local_mock_001",
                "object": "response",
                "status": "completed",
                "output": [],
                "model": "offline-fake-model",
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalModel)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    upstream_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        app = create_app(
            {"/openai": (upstream_url, "openai")},
            launch_agent="codex",
        )
        # The actual CYT forwarder uses streaming HTTP responses, so use a
        # real loopback listener rather than MockTransport's consumed stream.
        async with httpx.AsyncClient(timeout=30.0) as upstream:
            app.state.http_client = upstream
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://cyt-offline.local",
                timeout=30.0,
            ) as client:
                health = await client.get("/health")
                assert health.status_code == 200, health.text
                health_payload = health.json()
                assert health_payload.get("name") == "cyt"
                assert health_payload.get("agent") == "codex"

                request_body = {
                    "model": "offline-fake-model",
                    "input": [{
                        "type": "message",
                        "role": "user",
                        "content": [{
                            "type": "input_text",
                            "text": "Search local public documentation only",
                        }],
                    }],
                    "tools": [{
                        "type": "function",
                        "name": "mcp__local__search_docs",
                        "description": "Search local public docs",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    }],
                    "stream": False,
                }
                response = await client.post(
                    "/openai/v1/responses",
                    json=request_body,
                    headers={
                        "content-type": "application/json",
                        "authorization": "Bearer offline-inert-synthetic-test",
                    },
                )
                assert response.status_code == 200, response.text
                assert response.json()["id"] == "resp_cyt_local_mock_001"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    assert len(captured) == 1, "expected exactly one local fake-model call"
    observed = captured[0]
    assert observed["path"] == "/v1/responses", observed["path"]
    assert observed["body"]["model"] == "offline-fake-model"
    assert observed["body"].get("input")
    forwarded_tools = observed["body"].get("tools")
    assert isinstance(forwarded_tools, list) and forwarded_tools
    assert any(
        isinstance(item, dict) and item.get("name") == "mcp__local__search_docs"
        for item in forwarded_tools
    ), "relevant public tool was lost in proxy forwarding"

    return {
        "schema_version": 1,
        "kind": "cyt_native_openai_proxy_loopback_transport_compatibility",
        "status": "unscored_local_http_mock_pass",
        "proxy_agent_route": health_payload.get("agent"),
        "proxy_path": "/openai/v1/responses",
        "local_mock_upstream_path": observed["path"],
        "local_http_requests": len(captured),
        "input_tool_count": len(request_body["tools"]),
        "forwarded_tool_count": len(forwarded_tools),
        "real_model_calls": 0,
        "external_network_requests": 0,
        "live_mcp_calls": 0,
        "credentialed_provider_calls": 0,
        "codex_agent_started": False,
        "native_hook_verified": False,
        "tool_dispatch_blocking_verified": False,
        "cache_economics_measured": False,
        "heldout_performance_evidence": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(probe())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CYT native Proxy -> local HTTP fake model forwarding passed")


if __name__ == "__main__":
    main()

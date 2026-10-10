"""Exercise a genuine CYT Proxy OpenAI HTTP path against a local mock model.

This is *not* a Codex agent, MCP server, model completion, tool-blocking, or
held-out benchmark. No real network/model credentials; the outbound upstream
HTTP client is an in-memory httpx.MockTransport by construction.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any


async def probe() -> dict[str, Any]:
    import httpx

    from cyt.proxy.reverse import create_app

    sent: list[dict[str, Any]] = []

    def fake_model(request: httpx.Request) -> httpx.Response:
        # Deliberately no outbound TCP or real model provider.
        if request.method != "POST":
            raise ValueError("unexpected non-POST mock upstream request")
        request_body = json.loads(request.content)
        sent.append({
            "path": request.url.path,
            "method": request.method,
            "body": request_body,
        })
        return httpx.Response(
            200,
            json={
                "id": "resp_mock_cyt_offline_001",
                "object": "response",
                "status": "completed",
                "output": [],
                "model": "offline-fake-model",
            },
        )

    # The upstream URL is deliberately invalid outside the in-memory HTTP
    # transport, preventing accidental access to a real provider.
    app = create_app(
        {"/openai": ("https://mock-provider.invalid", "openai")},
        launch_agent="codex",
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(fake_model),
        timeout=30.0,
    ) as upstream:
        app.state.http_client = upstream
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://cyt-offline.local",
            timeout=30.0,
        ) as client:
            health = await client.get("/health")
            assert health.status_code == 200, health.text
            status = health.json()
            assert status.get("name") == "cyt"
            assert status.get("agent") == "codex"

            request = {
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
                json=request,
                headers={
                    "content-type": "application/json",
                    # This is an intentionally inert synthetic test token.
                    "authorization": "Bearer offline-test-token-only",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["id"] == "resp_mock_cyt_offline_001"

    assert len(sent) == 1, f"mock provider intercepted {len(sent)} requests"
    observed = sent[0]
    assert observed["path"] == "/v1/responses", observed["path"]
    assert observed["body"]["model"] == "offline-fake-model"
    assert observed["body"].get("input")
    assert observed["body"]["tools"]
    assert any(
        item.get("name") == "mcp__local__search_docs"
        for item in observed["body"]["tools"]
    ), "native proxy failed to preserve the relevant safe public tool"

    return {
        "schema_version": 1,
        "kind": "cyt_offline_openai_proxy_http_transport_compatibility",
        "status": "unscored_mock_upstream_pass",
        "cyt_agent_route": status.get("agent"),
        "proxy_path": "/openai/v1/responses",
        "mock_upstream_path": observed["path"],
        "upstream_request_count": len(sent),
        "input_tool_count": len(request["tools"]),
        "forwarded_tool_count": len(observed["body"]["tools"]),
        "model_calls": 0,
        "live_mcp_calls": 0,
        "provider_credentials_used": False,
        "real_codex_agent_started": False,
        "real_model_task_success_measured": False,
        "proxy_blocking_verified": False,
        "hook_cyt_mcp_verified": False,
        "cache_economics_measured": False,
        "heldout_evidence": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(probe())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print("CYT Proxy -> mocked OpenAI responses HTTP forwarding validated")


if __name__ == "__main__":
    main()

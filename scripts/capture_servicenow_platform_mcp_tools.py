"""Capture the native ServiceNow Platform MCP readonly tools/list surface."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any


PINNED_UPSTREAM_REVISION = "5bcb83b29ab5b30aee07cabaa8df974881c47126"
EXPECTED_PUBLIC_TOOLS = 12


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


async def capture(*, upstream_revision: str) -> dict[str, Any]:
    os.environ.setdefault("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    os.environ.setdefault("SERVICENOW_OAUTH_CLIENT_ID", "schemarouter-benchmark-public-client")
    os.environ["MCP_TOOL_PACKAGE"] = "readonly"
    os.environ["SERVICENOW_ENV"] = "prod"
    os.environ.pop("SERVICENOW_USERNAME", None)
    os.environ.pop("SERVICENOW_PASSWORD", None)
    os.environ.pop("SERVICENOW_API_KEY", None)

    from servicenow_mcp.server import create_mcp_server

    mcp = create_mcp_server()
    async with mcp._lowlevel_server.lifespan(mcp._lowlevel_server):
        tools = await mcp.list_tools()

    raw_tools = [
        tool.model_dump(mode="json", by_alias=True, exclude_none=True)
        for tool in tools
    ]
    names = [tool.get("name") for tool in raw_tools]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("captured MCP tool without a valid name")
    if len(names) != len(set(names)):
        raise ValueError("captured duplicate MCP tool names")
    if len(raw_tools) != EXPECTED_PUBLIC_TOOLS:
        raise ValueError(
            f"readonly tool count drifted: expected {EXPECTED_PUBLIC_TOOLS}, "
            f"captured {len(raw_tools)}"
        )

    digest = hashlib.sha256(_canonical(raw_tools)).hexdigest()
    return {
        "schema_version": 1,
        "source": {
            "repository": "Xerrion/servicenow-platform-mcp",
            "commit": upstream_revision,
            "package_version": importlib.metadata.version("servicenow-platform-mcp"),
            "python_package": "servicenow-platform-mcp",
        },
        "mcp_tool_package": "readonly",
        "servicenow_environment": "prod",
        "capture": {
            "api": "MCPServer.list_tools",
            "live_credentials_required": False,
            "tool_execution": False,
            "network_calls_required": False,
            "native_order_preserved": True,
        },
        "tool_count": len(raw_tools),
        "tools_sha256": digest,
        "tools": raw_tools,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--upstream-revision",
        default=PINNED_UPSTREAM_REVISION,
        help="Exact upstream revision represented by the installed checkout.",
    )
    args = parser.parse_args()

    if args.upstream_revision != PINNED_UPSTREAM_REVISION:
        raise ValueError(
            "development fixture is pinned to "
            f"{PINNED_UPSTREAM_REVISION}; update the manifest before changing it"
        )

    payload = asyncio.run(capture(upstream_revision=args.upstream_revision))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "tool_count": payload["tool_count"],
                "tools_sha256": payload["tools_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

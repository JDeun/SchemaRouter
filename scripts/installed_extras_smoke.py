from __future__ import annotations

import json
from importlib.metadata import version

import httpx2
import typesafe_sdk
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.sdk.trace import TracerProvider

from schemarouter import DefaultMCPClientFactory
import schemarouter.integrations as integrations
from schemarouter.integrations import OpenTelemetryRunExporter


def run_smoke() -> dict[str, object]:
    tracer = TracerProvider().get_tracer("schemarouter-installed-extras-smoke")
    exporter = OpenTelemetryRunExporter(tracer)
    mcp_factory = DefaultMCPClientFactory()
    installed_version = version("schemarouter")
    historical_jev = installed_version == "0.17.0"
    if historical_jev:
        # The still-published v0.17 wheel owns this historical integration.
        backend = getattr(integrations, "JevDecisionBackend")
        assert backend(client=object()).client is not None
    else:
        assert not hasattr(integrations, "JevDecisionBackend")

    assert callable(streamable_http_client)
    assert Client is not None
    assert httpx2.AsyncClient is not None
    assert typesafe_sdk is not None
    assert exporter.tracer is tracer
    assert mcp_factory is not None

    return {
        "status": "success",
        "dependencies": {
            "mcp": version("mcp"),
            "typesafe-sdk": version("typesafe-sdk"),
            "opentelemetry-sdk": version("opentelemetry-sdk"),
        },
        "integrations": [
            "mcp",
            *(["jev"] if historical_jev else []),
            "opentelemetry",
        ],
    }


def main() -> None:
    print(json.dumps(run_smoke(), sort_keys=True))


if __name__ == "__main__":
    main()

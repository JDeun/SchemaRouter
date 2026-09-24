from __future__ import annotations

import json
from importlib.metadata import version

import typesafe_sdk
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.sdk.trace import TracerProvider

from schemarouter import DefaultMCPClientFactory
from schemarouter.integrations import JevDecisionBackend, OpenTelemetryRunExporter


def run_smoke() -> dict[str, object]:
    tracer = TracerProvider().get_tracer("schemarouter-installed-extras-smoke")
    exporter = OpenTelemetryRunExporter(tracer)
    mcp_factory = DefaultMCPClientFactory()
    jev = JevDecisionBackend(client=object())

    assert callable(streamable_http_client)
    assert Client is not None
    assert typesafe_sdk is not None
    assert exporter.tracer is tracer
    assert mcp_factory is not None
    assert jev.client is not None

    return {
        "status": "success",
        "dependencies": {
            "mcp": version("mcp"),
            "typesafe-sdk": version("typesafe-sdk"),
            "opentelemetry-sdk": version("opentelemetry-sdk"),
        },
        "integrations": [
            "mcp",
            "jev",
            "opentelemetry",
        ],
    }


def main() -> None:
    print(json.dumps(run_smoke(), sort_keys=True))


if __name__ == "__main__":
    main()

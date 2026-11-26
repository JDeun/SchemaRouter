from __future__ import annotations

import json
from importlib import import_module
from importlib.metadata import distribution, version
from importlib.util import find_spec

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from opentelemetry.sdk.trace import TracerProvider

import schemarouter
import schemarouter.integrations as integrations
from schemarouter import DefaultMCPClientFactory
from schemarouter.integrations import OpenTelemetryRunExporter


def run_smoke() -> dict[str, object]:
    tracer = TracerProvider().get_tracer("schemarouter-installed-extras-smoke")
    exporter = OpenTelemetryRunExporter(tracer)
    mcp_factory = DefaultMCPClientFactory()
    installed_version = version("schemarouter")
    historical_jev = installed_version == "0.17.0"
    dependencies = {
        "mcp": version("mcp"),
        "opentelemetry-sdk": version("opentelemetry-sdk"),
    }
    if historical_jev:
        # The still-published v0.17 wheel owns this historical integration.
        backend = import_module("schemarouter.integrations.jev").JevDecisionBackend
        assert backend(client=object()).client is not None
        assert import_module("typesafe_sdk") is not None
        dependencies["typesafe-sdk"] = version("typesafe-sdk")
    else:
        # This runs against a real installed wheel, not only the source tree.
        for symbol in (
            "DECISION_BACKEND_ENTRY_POINT_GROUP",
            "CallableDecisionBackend",
            "DecisionBackend",
            "DecisionCallable",
            "DecisionOption",
            "DecisionOptionTextCallable",
            "DecisionRequest",
            "DecisionResult",
            "DecisionSelection",
            "EmbeddingCallable",
            "EmbeddingDecisionBackend",
            "FirstOptionDecisionBackend",
            "choose_async",
            "choose_sync",
            "DecisionBackendPluginInfo",
            "discover_decision_backend_plugins",
            "load_decision_backend_plugin",
        ):
            assert not hasattr(schemarouter, symbol), symbol
        for symbol in (
            "JevDecisionBackend",
            "LayaDecisionBackend",
            "OllamaDecisionBackend",
            "SystemOneDecisionBackend",
            "MicrosoftDecisionOneFoundryBackend",
        ):
            assert not hasattr(integrations, symbol), symbol
        for module in (
            "schemarouter.decision_plugins",
            "schemarouter.decisions",
            "schemarouter.integrations.jev",
            "schemarouter.integrations.laya",
            "schemarouter.integrations.ollama",
            "schemarouter.integrations.system_one",
            "schemarouter.integrations.microsoft_decision",
        ):
            assert find_spec(module) is None, module
        package = distribution("schemarouter")
        retired_extras = {"jev", "systemone", "laya"}
        assert retired_extras.isdisjoint(package.metadata.get_all("Provides-Extra") or [])
        for requirement in package.requires or []:
            assert not requirement.lower().startswith(("typesafe-sdk", "laya"))
        files = package.files
        assert files is not None
        assert not any(
            "research_legacy_decision_adapters" in path.parts
            or path.name == "research_legacy_decisions.py"
            for path in files
        )

    assert callable(streamable_http_client)
    assert Client is not None
    assert httpx2.AsyncClient is not None
    assert exporter.tracer is tracer
    assert mcp_factory is not None

    return {
        "status": "success",
        "dependencies": dependencies,
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

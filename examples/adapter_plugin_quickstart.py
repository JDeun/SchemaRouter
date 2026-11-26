"""Run the separately packaged third-party SourceAdapter example.

Install the example package first:

    python -m pip install -e examples/adapter_plugin_demo
"""

from __future__ import annotations

import asyncio
import sys

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall, discover_adapter_plugins

PLUGIN_ENTRY_POINT = "demo_static"
PLUGIN_MODULE = "schemarouter_demo_adapter"


async def main() -> None:
    assert PLUGIN_MODULE not in sys.modules

    discovered = {plugin.name: plugin for plugin in discover_adapter_plugins()}
    plugin = discovered[PLUGIN_ENTRY_POINT]
    assert plugin.value == "schemarouter_demo_adapter:DemoStaticAdapter"

    # Metadata-only discovery must not import third-party code.
    assert PLUGIN_MODULE not in sys.modules

    router = SchemaRouter()
    loaded_kinds = router.load_adapter_plugins(allowlist={PLUGIN_ENTRY_POINT})
    assert loaded_kinds == ("demo_static",)
    assert PLUGIN_MODULE in sys.modules

    tool = await router.add_url(
        "https://example.invalid/demo-static",
        kind="demo_static",
        name="demo_catalog",
    )
    # The host knows the plugin's registered route and supplies its own inputs.
    endpoint = tool.endpoint("lookup")
    plan = ExecutionPlan(
        query="demo value",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"item_id": "alpha"},
                fields=["value"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )
    result = (await router.execute(plan))[0]
    assert result.data == {"value": 5}

    print(
        {
            "discovered_without_import": True,
            "loaded_adapter_kind": loaded_kinds[0],
            "result": result.data,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

"""Run the separately packaged third-party SourceAdapter example.

Install the example package first:

    python -m pip install -e examples/adapter_plugin_demo
"""

from __future__ import annotations

import asyncio
import sys

from schemarouter import PlanRequest, SchemaRouter, discover_adapter_plugins

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
    plan = router.plan(
        PlanRequest(
            query="demo value",
            preferred_tools=[tool.key],
            arguments={"item_id": "alpha"},
        )
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

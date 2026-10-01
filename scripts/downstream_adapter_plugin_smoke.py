"""Downstream installed-wheel smoke for third-party SourceAdapter entry points.

This script is intended to run in a clean consumer-style virtual environment where
SchemaRouter was installed from the wheel built by CI and the demo adapter was
installed as a separate distribution.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import schemarouter
from schemarouter import (
    ExecutionPolicy,
    PlanRequest,
    PolicyRule,
    PolicyViolationError,
    SchemaRouter,
    SchemaValidationError,
    discover_adapter_plugins,
)

PLUGIN_ENTRY_POINT = "demo_static"
PLUGIN_MODULE = "schemarouter_demo_adapter"
PLUGIN_VALUE = "schemarouter_demo_adapter:DemoStaticAdapter"
PLUGIN_SOURCE = "https://example.invalid/demo-static"


def _assert_installed_wheel_import() -> None:
    package_file = Path(schemarouter.__file__).resolve()
    repository_root = Path(__file__).resolve().parents[1]

    assert repository_root not in package_file.parents, (
        "downstream smoke imported SchemaRouter from the repository source tree "
        f"instead of the installed wheel: {package_file}"
    )
    assert "site-packages" in package_file.parts, package_file


def _plan(router: SchemaRouter, tool_key: str, item_id: str):
    return router.plan(
        PlanRequest(
            query="demo value",
            preferred_tools=[tool_key],
            arguments={"item_id": item_id},
        )
    )


async def main() -> None:
    _assert_installed_wheel_import()

    sys.modules.pop(PLUGIN_MODULE, None)
    sys.modules.pop(f"{PLUGIN_MODULE}.adapter", None)

    discovered = {plugin.name: plugin for plugin in discover_adapter_plugins()}
    plugin = discovered[PLUGIN_ENTRY_POINT]
    assert plugin.value == PLUGIN_VALUE

    # Entry-point metadata discovery must not execute installed plugin code.
    assert PLUGIN_MODULE not in sys.modules

    router = SchemaRouter()
    loaded = router.load_adapter_plugins(allowlist={PLUGIN_ENTRY_POINT})
    assert loaded == ("demo_static",)
    assert PLUGIN_MODULE in sys.modules

    tool = await router.add_url(
        PLUGIN_SOURCE,
        kind="demo_static",
        name="demo_catalog",
    )

    valid_result = (await router.execute(_plan(router, tool.key, "alpha")))[0]
    assert valid_result.data == {"value": 5}

    # If an adapter plugin could bypass SchemaRouter input validation, this would
    # reach its invoker and return {"value": 0}. It must fail before invocation.
    try:
        await router.execute(_plan(router, tool.key, ""))
    except SchemaValidationError:
        pass
    else:
        raise AssertionError(
            "adapter plugin bypassed SchemaRouter input-schema validation"
        )

    denied_router = SchemaRouter(
        policy=ExecutionPolicy(
            rules=(
                PolicyRule(
                    effect="deny",
                    operation="demo_catalog.lookup",
                    name="downstream-smoke-deny",
                ),
            )
        )
    )
    denied_router.load_adapter_plugins(allowlist={PLUGIN_ENTRY_POINT})
    denied_tool = await denied_router.add_url(
        PLUGIN_SOURCE,
        kind="demo_static",
        name="demo_catalog",
    )

    # A plugin-supplied invoker must not bypass trusted local execution policy.
    try:
        await denied_router.execute(_plan(denied_router, denied_tool.key, "alpha"))
    except PolicyViolationError:
        pass
    else:
        raise AssertionError(
            "adapter plugin bypassed SchemaRouter execution policy"
        )

    print(
        {
            "schemarouter_import": str(Path(schemarouter.__file__).resolve()),
            "discovered_without_import": True,
            "loaded_adapter_kind": loaded[0],
            "validated_result": valid_result.data,
            "invalid_input_blocked": True,
            "local_policy_blocked": True,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

import pytest

from schemarouter import PlanRequest, SchemaRouter
from schemarouter.adapters import plugins


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE = ROOT / "examples" / "adapter_plugin_demo" / "src"
PLUGIN_MODULE = "schemarouter_demo_adapter"
PLUGIN_ENTRY_POINT = "demo_static"


def _example_entry_points() -> importlib.importlib.metadata.EntryPoints:
    return importlib.importlib.metadata.EntryPoints(
        [
            importlib.metadata.EntryPoint(
                name=PLUGIN_ENTRY_POINT,
                value=f"{PLUGIN_MODULE}:DemoStaticAdapter",
                group=plugins.ADAPTER_ENTRY_POINT_GROUP,
            )
        ]
    )


@pytest.mark.asyncio
async def test_runnable_adapter_plugin_example_requires_explicit_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(PLUGIN_SOURCE))
    sys.modules.pop(PLUGIN_MODULE, None)
    sys.modules.pop(f"{PLUGIN_MODULE}.adapter", None)
    monkeypatch.setattr(
        plugins.metadata,
        "entry_points",
        _example_entry_points,
    )

    discovered = plugins.discover_adapter_plugins()

    assert [plugin.name for plugin in discovered] == [PLUGIN_ENTRY_POINT]
    assert discovered[0].value == f"{PLUGIN_MODULE}:DemoStaticAdapter"
    assert PLUGIN_MODULE not in sys.modules

    router = SchemaRouter()
    assert router.load_adapter_plugins(allowlist={PLUGIN_ENTRY_POINT}) == (
        "demo_static",
    )
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


def test_adapter_plugin_example_declares_real_entry_point() -> None:
    pyproject = (
        ROOT / "examples" / "adapter_plugin_demo" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert '[project.entry-points."schemarouter.adapters"]' in pyproject
    assert (
        'demo_static = "schemarouter_demo_adapter:DemoStaticAdapter"'
        in pyproject
    )

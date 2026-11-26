"""The source-only historical router owns its dispatch rather than the product."""

from __future__ import annotations

import pytest

from schemarouter import PlanRequest, PolicyViolationError, SchemaRouter, schema_tool
from scripts.research_legacy_router import legacy_router
from scripts.research_legacy_runtime import LegacySchemaRouter


def test_research_router_constructs_without_product_legacy_mode(monkeypatch):
    original = SchemaRouter.__init__

    def forbid_legacy_constructor(self, **kwargs):
        assert not kwargs.get("_legacy_routing")
        original(self, **kwargs)

    def forbidden(*_args, **_kwargs):
        pytest.fail("research used installed legacy dispatch")

    monkeypatch.setattr(SchemaRouter, "__init__", forbid_legacy_constructor)
    for name in ("_legacy_plan", "_alegacy_plan", "retrieve", "aretrieve"):
        monkeypatch.setattr(SchemaRouter, name, forbidden)

    @schema_tool(read_only=True)
    def lookup(value: str) -> str:
        return value

    router = legacy_router()
    assert isinstance(router, LegacySchemaRouter)
    key = router.add_callable(lookup)
    request = PlanRequest(query="lookup", preferred_tools=[key], arguments={"value": "ok"})
    assert router.plan(request).calls[0].tool == key
    assert router.retrieve(request).candidates[0].tool == key


def test_default_router_remains_fail_closed():
    router = SchemaRouter()
    assert router.planner is None
    with pytest.raises(PolicyViolationError, match="lexical planning is unavailable"):
        router.plan("lookup")

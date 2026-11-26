"""Historical lexical snapshot/availability compatibility regressions."""
from __future__ import annotations

import pytest

from schemarouter import PolicyViolationError, SchemaRouter
from schemarouter._source_availability import _SourceAvailability
from test_native_source_pass_cache import _lookup, _router


def _legacy_router(**kwargs):
    return SchemaRouter(_legacy_routing=True, **kwargs)


def test_shared_source_authority_keeps_exact_snapshot_fingerprints_and_legacy_override(monkeypatch):
    router, posting, _graph = _router(monkeypatch, 4, router_factory=_legacy_router)
    authority = router._source_availability
    assert not hasattr(router.planner, "_snapshot_tool_fingerprint")
    index = router.planner._index()
    tool = index.tools[0]
    detached = tool.model_copy(deep=True)
    detached.description = "a different contract"
    assert authority.snapshot is index.fingerprints
    assert authority.snapshot.get(detached) is None
    assert authority.fingerprint(tool) == tool.fingerprint
    assert authority.fingerprint(detached) == detached.fingerprint != tool.fingerprint

    # Existing host overrides remain authoritative for native lookup.
    callback = lambda _tool, _endpoint: False  # noqa: E731
    monkeypatch.setattr(router.planner, "availability_predicate", callback)
    assert router._source_availability_predicate() is callback
    assert _lookup(posting, router).status == "no_proven_hit"


def test_native_lookup_rejects_replaced_legacy_availability_owner(monkeypatch):
    router, posting, _graph = _router(monkeypatch, 4, router_factory=_legacy_router)
    monkeypatch.setattr(
        router.planner, "_source_availability",
        _SourceAvailability(router._source_availability_predicate()),
    )
    with pytest.raises(PolicyViolationError, match="source availability mismatch"):
        _lookup(posting, router)

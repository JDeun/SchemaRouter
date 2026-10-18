"""Synthetic numeric-only E0 cost controls, not routing success claims."""
from __future__ import annotations

import json

import pytest

from schemarouter import SchemaRouter
from scripts.research_scoped_catalog_byte_cost_e0 import profile


def test_scoped_index_and_schema_bytes_are_measured_without_model() -> None:
    report = profile(sizes=(100, 250), roles=("viewer", "editor"))
    assert report["study"] == "SYNTHETIC_AUTHORIZED_CATALOG_BYTE_COST_E0"
    assert report["independent_e2"] is False
    assert report["measured_tokens"] is False
    assert report["proves_routing_accuracy"] is False
    assert report["model_calls"] == report["execution_calls"] == 0
    assert len(report["rows"]) == 4
    for row in report["rows"]:
        assert row["selected_count"] <= 5
        assert row["full_selected_k5_schema_bytes"] > 2
        assert row["first_selected_schema_bytes"] > 2
        if row["index_status"] == "complete_authorized_catalog":
            assert isinstance(row["index_bytes"], int)
            assert row["index_bytes"] > 2
            assert row["index_plus_one_detail_bytes"] == (
                row["index_bytes"] + row["first_selected_schema_bytes"]
            )
        else:
            assert row["index_status"] == "rejected_oversize_complete_catalog"
            assert row["index_bytes"] is None
            assert row["index_plus_one_detail_bytes"] is None
    payload = json.dumps(report)
    assert "invoice total amount" not in payload
    assert "benchapi.probe" not in payload
    assert "required_routes" not in payload


def test_index_overflow_is_a_visible_rejection_not_a_partial_catalog() -> None:
    result = profile(sizes=(100,), roles=("viewer",), max_index_bytes=8)
    row = result["rows"][0]
    assert row["index_status"] == "rejected_oversize_complete_catalog"
    assert row["index_bytes"] is None
    assert row["index_plus_one_detail_bytes"] is None
    assert row["execution_calls"] == row["model_calls"] == 0


def test_metadata_only_scale_at_500_routes_does_not_increase_k() -> None:
    result = profile(sizes=(500,), roles=("viewer",))
    row = result["rows"][0]
    assert row["synthetic_catalog_size"] == 500
    assert 0 < row["visible_route_count"] <= 500
    assert row["selected_count"] <= 5
    assert result["strict_selected_k"] == 5


def test_cost_measurement_never_invokes_agent_or_router_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("catalog profiling executed a tool or planned a step")

    monkeypatch.setattr(SchemaRouter, "plan", forbidden)
    monkeypatch.setattr(SchemaRouter, "execute", forbidden)
    assert profile(sizes=(100,), roles=("viewer",))["model_calls"] == 0


@pytest.mark.parametrize("kwargs", (
    {"sizes": []}, {"sizes": (100, 100)}, {"sizes": (True,)},
    {"sizes": (99,)}, {"roles": ()}, {"roles": ("viewer", "viewer")},
    {"roles": ("root",)}, {"max_index_bytes": 0},
    {"max_index_bytes": True}, {"max_index_bytes": 131073},
))
def test_cost_study_rejects_unregistered_configs(kwargs) -> None:
    with pytest.raises(ValueError):
        profile(**kwargs)

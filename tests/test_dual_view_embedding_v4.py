from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_dual_view_embedding_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_dual_view_embedding_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load dual-view diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Field:
    def __init__(
        self,
        name: str,
        *,
        semantic_id: str | None = None,
        identifier: bool = False,
    ) -> None:
        self.name = name
        self.semantic_id = semantic_id
        self.identifier = identifier


class _Endpoint:
    name = "create_ticket"
    description = "Create a customer support ticket"
    operation_aliases = ["create support ticket", "open support case"]
    output_fields = [
        _Field("ticket_id", identifier=True),
        _Field("status", semantic_id="ticket_status"),
    ]


class _Tool:
    key = "support"
    description = "Customer support operations"


def test_route_views_separate_schema_and_action_surfaces() -> None:
    module = _module()
    schema = module._schema_text(_Tool(), _Endpoint())
    action = module._action_text(_Endpoint())

    assert "support.create_ticket" in schema
    assert "Customer support operations" in schema
    assert "Create a customer support ticket" in schema
    assert "ticket_status" in schema
    assert "ticket_id" not in schema

    assert action.splitlines() == [
        "create ticket",
        "create support ticket",
        "open support case",
    ]
    assert "Customer support operations" not in action


def test_factorized_routing_uses_schema_tool_then_action_endpoint() -> None:
    module = _module()
    catalog = [
        {
            "route_id": "alpha.search",
            "tool": "alpha",
            "endpoint": "search",
        },
        {
            "route_id": "alpha.update",
            "tool": "alpha",
            "endpoint": "update",
        },
        {
            "route_id": "beta.search",
            "tool": "beta",
            "endpoint": "search",
        },
        {
            "route_id": "beta.update",
            "tool": "beta",
            "endpoint": "update",
        },
    ]
    result = module._factorized(
        catalog,
        schema_scores=[0.8, 0.7, 0.4, 0.3],
        action_scores=[0.2, 0.9, 0.95, 0.1],
    )
    assert result["selected_route"] == "alpha.update"
    assert result["top_score"] == 0.8
    assert result["top_margin"] > 0.0


def test_projection_keeps_full_population_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "category": "v4_supported_natural",
            "selected_route": "tool.a",
            "top_score": 0.9,
            "top_margin": 0.2,
            "schema_action_top_tool_agree": True,
            "schema_action_top_route_agree": True,
        },
        {
            "expected": "tool.a",
            "category": "v4_supported_natural",
            "selected_route": "tool.a",
            "top_score": 0.1,
            "top_margin": 0.01,
            "schema_action_top_tool_agree": True,
            "schema_action_top_route_agree": True,
        },
        {
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "selected_route": "tool.a",
            "top_score": 0.2,
            "top_margin": 0.02,
            "schema_action_top_tool_agree": True,
            "schema_action_top_route_agree": True,
        },
    ]
    projected = module._project(
        rows,
        thresholds={
            "tool.a": {
                "min_score": 0.5,
                "min_margin": 0.1,
            }
        },
        agreement_mode="none",
    )
    assert projected["supported_exact_route_accuracy"] == 0.5
    assert projected["near_domain_unsupported_rejection"] == 1.0
    assert projected["false_routes"] == 0


def test_agreement_gate_is_explicit() -> None:
    module = _module()
    row = {
        "schema_action_top_tool_agree": True,
        "schema_action_top_route_agree": False,
    }
    assert module._agreement_passes(row, "none")
    assert module._agreement_passes(
        row,
        "schema_action_top_tool_agree",
    )
    assert not module._agreement_passes(
        row,
        "schema_action_top_route_agree",
    )

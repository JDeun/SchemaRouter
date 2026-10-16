"""Read-only DEV lower-bound experiments cannot become policy authority."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy, AuthorizationRule, DataScopeRule, EndpointSpec,
    FieldSpec, HostFieldContract, PrincipalContext, SchemaRouter, ToolSpec,
    select_authorized_field_contract,
)
from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import build_fixture
from scripts.research_host_exact_field_scan_lower_bound_dev import (
    CASES, _matches, _metrics, assess, direct_scan,
)


def field_contract(*names: str) -> HostFieldContract:
    return HostFieldContract(operation="read", required_output_fields=list(names))


def small_router(*, hidden: bool = False) -> SchemaRouter:
    policy = AuthorizationPolicy(
        rules=(AuthorizationRule(
            name="allow-reader", effect="allow", operation="*.*",
            roles_any=("viewer",),
        ),),
        default_effect="deny",
        data_rules=(DataScopeRule(
            operation="locked.read", roles_any=("viewer",),
            hidden_fields=("secret",),
        ),) if hidden else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(ToolSpec(
        name="locked", description="Internal lookup",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(name="secret")],
        )],
    ))
    return router


def test_one_hundred_route_public_selector_parity_all_18_dev_cases() -> None:
    report = assess(sizes=(100,), repeats=1)
    assert report["sizes"] == [100]
    assert report["statistics"]["100"]["cases"] == 18
    assert report["statistics"]["100"]["parity"] is True
    assert len(report["rows"]) == len(CASES) * 3
    assert {r["language"] for r in report["rows"]} == {"en", "ko", "ja"}
    assert all(r["complete_visible_count"] == 95 for r in report["rows"])
    assert report["boundaries"]["product_API_modified"] is False
    assert report["boundaries"]["may_release"] is False


def test_ambiguous_and_hidden_source_fields_are_not_promoted() -> None:
    router, _ = build_fixture(100)
    who = principal("viewer")
    ambiguous = direct_scan(router, who, field_contract("payload"))
    assert ambiguous["reason"] == "ambiguous_contract_match"
    assert ambiguous["selected_route_id"] is None
    assert len(ambiguous["matching_route_ids"]) >= 2
    assert direct_scan(
        router, who, field_contract("audit_tag"),
    )["reason"] == "no_contract_match"


def test_denied_principal_receives_no_source_metadata() -> None:
    router = small_router()
    outsider = PrincipalContext(subject="outsider", roles=("outsider",))
    result = direct_scan(router, outsider, field_contract("secret"))
    assert result == {
        "reason": "empty_authorized_catalog", "selected_route_id": None,
        "matching_route_ids": [], "visible_candidate_count": 0,
    }


def test_fully_hidden_endpoint_is_not_counted_as_visible() -> None:
    router = small_router(hidden=True)
    who = PrincipalContext(subject="viewer", roles=("viewer",))
    result = direct_scan(router, who, field_contract("secret"))
    public = select_authorized_field_contract(
        router, "read secret", principal=who,
        contract=field_contract("secret"), k=1,
    )
    assert result["reason"] == public.reason == "empty_authorized_catalog"
    assert result["visible_candidate_count"] == public.candidate_count == 0


def test_local_availability_denial_is_respected() -> None:
    router = small_router()
    who = PrincipalContext(subject="viewer", roles=("viewer",))
    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "locked"
    )
    direct = direct_scan(router, who, field_contract("secret"))
    public = select_authorized_field_contract(
        router, "read secret", principal=who,
        contract=field_contract("secret"), k=1,
    )
    assert direct["reason"] == public.reason == "empty_authorized_catalog"


def test_registry_change_mid_scan_fails_closed() -> None:
    router = small_router()
    who = PrincipalContext(subject="viewer", roles=("viewer",))
    old_tools = router.registry.tools
    changed = False

    def mutate_once():
        nonlocal changed
        tools = old_tools()
        if not changed:
            changed = True
            router.add_tool(ToolSpec(
                name="new", description="Synthetic subsequent update",
                endpoints=[EndpointSpec(
                    name="read", read_only=True,
                    output_fields=[FieldSpec(name="new_field")],
                )],
            ))
        return tools

    router.registry.tools = mutate_once
    with pytest.raises(ValueError, match="scope changed mid-scan"):
        direct_scan(router, who, field_contract("secret"))


@pytest.mark.parametrize("size,repeats", [
    ((100,), 0), ((100, 100), 1), ((777,), 1),
    ((100,), 4), ([100], 1), ((True,), 1),
])
def test_unregistered_experiment_fails_before_any_fetch(size, repeats) -> None:
    with pytest.raises(ValueError, match="nonregistered"):
        assess(sizes=size, repeats=repeats)


def test_nonfinite_or_empty_metrics_rejected() -> None:
    for values in ([], [0.0], [float("nan")], [float("inf")], [-1.0]):
        with pytest.raises(ValueError):
            _metrics(values)


def test_write_endpoint_and_wrong_declared_fields_do_not_match() -> None:
    writable = EndpointSpec(
        name="write", read_only=False, destructive=True,
        output_fields=[FieldSpec(name="secret")],
    )
    assert not _matches(writable, field_contract("secret"))
    readable = EndpointSpec(
        name="read", read_only=True,
        output_fields=[FieldSpec(name="safe")],
    )
    assert not _matches(readable, field_contract("secret"))
    assert _matches(readable, field_contract("safe"))

"""Source-declared field-contract selection cannot execute or widen permissions."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.host_field_contract import (
    HostFieldContract,
    RequiredEnumValue,
    select_authorized_field_contract,
)


def _endpoint(
    name: str, values: list[str], *, output: str,
    writable: bool = False,
) -> EndpointSpec:
    return EndpointSpec(
        name=name, description=f"read {name} published data",
        read_only=not writable,
        destructive=writable,
        parameters=[
            ParameterSpec(
                name="hourly", location="query",
                json_schema={
                    "type": "array",
                    "items": {"type": "string", "enum": values},
                },
            ),
        ],
        output_fields=[
            FieldSpec(name=output),
            FieldSpec(name="sensitive_audit"),
        ],
    )


def _router(
    *,
    hidden: bool = False,
    deny_archive: bool = False,
) -> SchemaRouter:
    rules = [
        AuthorizationRule(
            name="deny-archive-viewer",
            effect="deny", operation="archive.*",
            roles_any=("viewer",),
        ),
    ] if deny_archive else []
    rules.append(AuthorizationRule(
        name="view-public", effect="allow", operation="*.*",
        roles_any=("viewer",),
    ))
    return_router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=tuple(rules), default_effect="deny",
            data_rules=(
                DataScopeRule(
                    operation="*.*", roles_any=("viewer",),
                    hidden_fields=("sensitive_audit",),
                ),
            ) if hidden else (),
        ),
    )
    return_router.add_tool(ToolSpec(
        name="marine", description="Ocean weather data",
        endpoints=[_endpoint(
            "read", ["wave_height", "ocean_current_velocity"],
            output="ocean_conditions",
        )],
    ))
    return_router.add_tool(ToolSpec(
        name="archive", description="Archive historical weather",
        endpoints=[_endpoint(
            "read", ["wave_height", "temperature_2m"],
            output="archive_values",
        )],
    ))
    return_router.add_tool(ToolSpec(
        name="forecast", description="Current forecast",
        endpoints=[_endpoint(
            "read", ["temperature_2m"], output="forecast_values",
        )],
    ))
    return return_router


def _contract(*variables: str, output: str | None = None) -> HostFieldContract:
    return HostFieldContract(
        operation="read",
        required_enums=[
            RequiredEnumValue(parameter="hourly", value=v)
            for v in variables
        ],
        required_output_fields=[output] if output else [],
    )


VIEWER = PrincipalContext(subject="host-verified-viewer", roles=("viewer",))
OUTSIDER = PrincipalContext(subject="unverified-outsider", roles=("outsider",))


def test_two_fields_unique_source_contract_selected_without_invocation() -> None:
    router = _router()
    # Ordinary query route scores may all be zero; only typed requirements
    # from the authenticated host, not cosine similarity, establish match.
    def not_allowed(*args, **kwargs):
        raise AssertionError("tool execute/planner cannot be called")
    router.execute = not_allowed
    router.plan = not_allowed
    decision = select_authorized_field_contract(
        router, "바다 파고와 해류를 알려줘",
        principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
    )
    assert decision.disposition == "selected"
    assert decision.selected_route_id == "marine.read"
    assert len(decision.selected_tool_fingerprint or "") > 8
    assert len(decision.selected_endpoint_fingerprint or "") > 8
    assert decision.registry_version == router.registry.version


def test_one_common_enum_abstains_even_if_first_rank_has_a_match() -> None:
    result = select_authorized_field_contract(
        _router(), PlanRequest(query="wave height"),
        principal=VIEWER, contract=_contract("wave_height"),
    )
    assert result.disposition == "abstained"
    assert result.reason == "ambiguous_contract_match"
    assert set(result.matching_route_ids) == {"archive.read", "marine.read"}
    assert result.selected_route_id is None


def test_missing_or_wrong_field_abstains() -> None:
    router = _router()
    result = select_authorized_field_contract(
        router, "temperature", principal=VIEWER,
        contract=_contract("unknown_field"),
    )
    assert result.reason == "no_contract_match"
    assert result.selected_route_id is None


def test_truncated_catalog_cannot_claim_unique_selection() -> None:
    result = select_authorized_field_contract(
        _router(), "ocean weather", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=1,
    )
    assert result.disposition == "abstained"
    assert result.reason == "incomplete_authorized_catalog"
    assert result.selected_route_id is None


def test_denied_principal_has_empty_catalog_and_never_dispatches() -> None:
    result = select_authorized_field_contract(
        _router(), "ocean", principal=OUTSIDER,
        contract=_contract("wave_height", "ocean_current_velocity"),
    )
    assert result.disposition == "abstained"
    assert result.reason == "empty_authorized_catalog"
    assert not result.matching_route_ids


def test_role_scope_does_not_allow_denied_alternative() -> None:
    result = select_authorized_field_contract(
        _router(deny_archive=True), "wave height",
        principal=VIEWER, contract=_contract("wave_height"),
    )
    assert result.selected_route_id == "marine.read"


def test_hidden_output_fields_do_not_reappear_in_selector() -> None:
    result = select_authorized_field_contract(
        _router(hidden=True), "ocean", principal=VIEWER,
        contract=_contract(
            "wave_height", "ocean_current_velocity",
            output="sensitive_audit",
        ),
    )
    assert result.reason == "no_contract_match"
    visible = select_authorized_field_contract(
        _router(hidden=True), "ocean", principal=VIEWER,
        contract=_contract(
            "wave_height", "ocean_current_velocity",
            output="ocean_conditions",
        ),
    )
    assert visible.selected_route_id == "marine.read"


def test_missing_rbac_policy_rejected_not_silently_unscoped() -> None:
    router = SchemaRouter()
    with pytest.raises(PolicyViolationError, match="explicit authorization"):
        select_authorized_field_contract(
            router, "marine", principal=VIEWER,
            contract=_contract("wave_height"),
        )


@pytest.mark.parametrize("bad", [
    {"operation": "write", "required_enums": [
        {"parameter": "hourly", "value": "wave_height"},
    ]},
    {"operation": "read", "required_enums": []},
    {"operation": "read", "required_output_fields": ["bad field"]},
    {"operation": "read", "required_enums": [
        {"parameter": "hourly", "value": "wave_height"},
        {"parameter": "hourly", "value": "wave_height"},
    ]},
])
def test_host_malformed_contract_cannot_be_constructed(bad: dict) -> None:
    with pytest.raises(ValueError):
        HostFieldContract.model_validate(bad)


def test_forged_contract_model_copy_cannot_bypass_validator() -> None:
    forged = _contract("wave_height").model_copy(
        update={"required_output_fields": ["invalid field"]},
    )
    with pytest.raises(PolicyViolationError, match="forged host"):
        select_authorized_field_contract(
            _router(), "marine", principal=VIEWER, contract=forged,
        )


@pytest.mark.parametrize("k", [0, -1, True, 5.0, 5001])
def test_invalid_k_is_rejected(k) -> None:
    with pytest.raises(ValueError, match="k must"):
        select_authorized_field_contract(
            _router(), "marine", principal=VIEWER,
            contract=_contract("wave_height"), k=k,
        )


def test_stale_version_is_not_an_authority_receipt() -> None:
    router = _router()
    original_retrieve = router.retrieve_authorized
    def make_stale(*args, **kwargs):
        result = original_retrieve(*args, **kwargs)
        return result.model_copy(update={
            "registry_version": result.registry_version + 1,
        })
    router.retrieve_authorized = make_stale
    with pytest.raises(PolicyViolationError, match="stale"):
        select_authorized_field_contract(
            router, "marine", principal=VIEWER,
            contract=_contract("wave_height"),
        )


def test_fake_retrieval_with_authorized_route_injection_is_rejected() -> None:
    router = _router()
    original_retrieve = router.retrieve_authorized
    def inject(*args, **kwargs):
        result = original_retrieve(*args, **kwargs)
        fake = result.candidates[0].model_copy(
            update={"route_id": "danger.delete"},
        )
        return result.model_copy(
            update={"candidates": [fake, *result.candidates[1:]]},
        )
    router.retrieve_authorized = inject
    with pytest.raises(PolicyViolationError, match="untrusted route identity"):
        select_authorized_field_contract(
            router, "ocean", principal=VIEWER,
            contract=_contract("wave_height"),
        )


def test_invalid_principal_copy_does_not_launder_roles() -> None:
    forged = VIEWER.model_copy(update={"roles": ("viewer", 7)})
    with pytest.raises(PolicyViolationError, match="principal"):
        select_authorized_field_contract(
            _router(), "ocean", principal=forged,
            contract=_contract("wave_height"),
        )

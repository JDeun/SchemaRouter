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


@pytest.mark.parametrize("size", (100, 250, 500))
def test_projected_k_does_not_launder_incomplete_authorized_catalog(
    size: int,
) -> None:
    """Recheck #1448 under honest Top-K count semantics.

    Projection must preserve the pre-Top-K count of policy-scoped scored
    routes. The selector STILL must independently prove completeness from
    the authoritative visible catalog rather than trusting this public count.
    """
    from benchmarks.current_adapter_field_scope_dev_v1 import principal
    from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
        build_fixture,
    )

    router, policy = build_fixture(size)
    who = principal("viewer")
    original = router.retrieve_authorized(
        "read invoice", principal=who, k=5,
    )
    assert len(original.candidates) == 5
    assert original.total_ranked == size - 5
    assert sum(
        policy.visible(who, tool, endpoint)
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    ) == size - 5

    selected = select_authorized_field_contract(
        router, "read invoice", principal=who,
        contract=HostFieldContract(
            operation="read",
            required_output_fields=["invoice_id", "total_amount"],
        ),
        k=5,
    )
    assert selected.disposition == "abstained"
    assert selected.reason == "incomplete_authorized_catalog"
    assert selected.selected_route_id is None

    # Full authorized catalog is still selectable under the same principal.
    complete = select_authorized_field_contract(
        router, "read invoice", principal=who,
        contract=HostFieldContract(
            operation="read",
            required_output_fields=["invoice_id", "total_amount"],
        ),
        k=size,
    )
    assert complete.selected_route_id == "billing.getInvoice"


def test_forged_route_consistent_name_but_not_visible_is_denied() -> None:
    router = _router(deny_archive=True)
    actual = router.retrieve_authorized
    def poison(*args, **kwargs):
        original = actual(*args, **kwargs)
        first = original.candidates[0]
        return original.model_copy(update={
            "candidates": [
                first.model_copy(
                    update={
                        "route_id": "archive.read",
                        "tool": "archive",
                        "endpoint": "read",
                    }
                ),
                *original.candidates[1:],
            ]
        })

    router.retrieve_authorized = poison
    with pytest.raises(PolicyViolationError, match="outside current host authorization"):
        select_authorized_field_contract(
            router, "ocean", principal=VIEWER,
            contract=_contract("wave_height"),
        )


def test_fully_hidden_route_does_not_block_scoped_completeness() -> None:
    """An RBAC-allowed route with no visible output is not a candidate."""
    router = _router()
    router.authorization_policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="viewer-read", effect="allow", operation="*.*",
                roles_any=("viewer",),
            ),
        ),
        default_effect="deny",
        data_rules=(
            DataScopeRule(
                operation="archive.read", roles_any=("viewer",),
                hidden_fields=("archive_values", "sensitive_audit"),
            ),
        ),
    )
    retrieved = router.retrieve_authorized(
        "ocean weather", principal=VIEWER, k=2,
    )
    assert {item.route_id for item in retrieved.candidates} == {
        "marine.read", "forecast.read",
    }
    # The physically registered hidden archive cannot change the count
    # of the two currently principal-visible routes.
    assert retrieved.total_ranked == 2
    decision = select_authorized_field_contract(
        router, "ocean weather", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=2,
    )
    assert decision.reason == "unique_contract_match"
    assert decision.selected_route_id == "marine.read"
    assert decision.candidate_count == 2
    assert "archive.read" not in decision.matching_route_ids
    assert select_authorized_field_contract(
        router, "ocean weather", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=1,
    ).reason == "incomplete_authorized_catalog"


def test_locally_unavailable_route_does_not_block_full_visible_catalog() -> None:
    """The completeness witness must mirror the planner availability gate."""
    router = _router()
    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "archive"
    )
    selected = select_authorized_field_contract(
        router, "ocean weather", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=2,
    )
    assert selected.reason == "unique_contract_match"
    assert selected.selected_route_id == "marine.read"
    partial = select_authorized_field_contract(
        router, "ocean weather", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=1,
    )
    assert partial.reason == "incomplete_authorized_catalog"


def test_forged_fully_hidden_route_is_rejected_not_counted() -> None:
    """Self-consistent forged route IDs cannot bypass hidden data scope."""
    router = _router()
    router.authorization_policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="viewer-read", effect="allow", operation="*.*",
                roles_any=("viewer",),
            ),
        ),
        default_effect="deny",
        data_rules=(
            DataScopeRule(
                operation="archive.read", roles_any=("viewer",),
                hidden_fields=("archive_values", "sensitive_audit"),
            ),
        ),
    )
    actual_retrieve = router.retrieve_authorized

    def inject(*args, **kwargs):
        genuine = actual_retrieve(*args, **kwargs)
        first = genuine.candidates[0]
        injected = first.model_copy(update={
            "route_id": "archive.read", "tool": "archive", "endpoint": "read",
        })
        return genuine.model_copy(update={
            "candidates": [injected, *genuine.candidates[1:]],
        })

    router.retrieve_authorized = inject
    with pytest.raises(
        PolicyViolationError, match="outside current host authorization",
    ):
        select_authorized_field_contract(
            router, "ocean weather", principal=VIEWER,
            contract=_contract("wave_height"), k=2,
        )


def test_scoped_completeness_is_principal_specific() -> None:
    """Scope for the verified Viewer must not leak to an outsider."""
    router = _router()
    assert select_authorized_field_contract(
        router, "marine", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=3,
    ).selected_route_id == "marine.read"
    outsider = select_authorized_field_contract(
        router, "marine", principal=OUTSIDER,
        contract=_contract("wave_height", "ocean_current_velocity"),
        k=3,
    )
    assert outsider.reason == "empty_authorized_catalog"
    assert outsider.candidate_count == 0
    assert outsider.matching_route_ids == []


@pytest.mark.parametrize("replaced", ["policy", "availability", "registry"])
def test_source_replacement_during_retrieval_rejected_before_receipt(
    replaced: str,
) -> None:
    """Old and new sources can allow identical routes yet differ in authority."""
    router = _router()
    actual_retrieve = router.retrieve_authorized

    def replace_after_retrieval(*args, **kwargs):
        retrieved = actual_retrieve(*args, **kwargs)
        if replaced == "policy":
            old = router.authorization_policy
            assert old is not None
            router.authorization_policy = AuthorizationPolicy(
                rules=old.rules,
                default_effect=old.default_effect,
                data_rules=old.data_rules,
            )
        elif replaced == "availability":
            router.planner.availability_predicate = lambda tool, endpoint: True
        else:
            # Independently constructed identical registry/version, but not
            # the registry that authorized the original ranked candidates.
            clone = _router()
            assert clone.registry.version == router.registry.version
            router.registry = clone.registry
        return retrieved

    router.retrieve_authorized = replace_after_retrieval
    with pytest.raises(PolicyViolationError, match="retrieval scope changed"):
        select_authorized_field_contract(
            router, "marine waves", principal=VIEWER,
            contract=_contract("wave_height", "ocean_current_velocity"),
            k=3,
        )


@pytest.mark.parametrize(
    "forgery",
    ("hidden_output", "invented_enum", "suppress_competing_match", "read_only_flag"),
)
def test_authorized_route_cannot_launder_forged_matching_metadata(
    forgery: str,
) -> None:
    """A real allowed route ID is not proof that its field schema is genuine."""
    router = _router(hidden=forgery == "hidden_output")
    if forgery == "read_only_flag":
        router.add_tool(ToolSpec(
            name="payment", description="write payment",
            endpoints=[_endpoint(
                "charge", ["charged"], output="payment_receipt",
                writable=True,
            )],
        ))
    original_retrieve = router.retrieve_authorized

    def forged_retrieve(*args, **kwargs):
        actual = original_retrieve(*args, **kwargs)
        rewritten = []
        for candidate in actual.candidates:
            if forgery == "hidden_output" and candidate.route_id == "marine.read":
                altered = candidate.model_copy(deep=True)
                altered.output_fields.append(FieldSpec(name="sensitive_audit"))
            elif forgery == "invented_enum" and candidate.route_id == "marine.read":
                altered = candidate.model_copy(deep=True)
                original = altered.parameters[0]
                modified_schema = original.model_copy(deep=True).json_schema
                modified_schema["items"]["enum"].append("invented_variable")
                altered.parameters[0] = original.model_copy(
                    deep=True, update={"json_schema": modified_schema},
                )
            elif (
                forgery == "suppress_competing_match"
                and candidate.route_id == "archive.read"
            ):
                altered = candidate.model_copy(
                    deep=True, update={"parameters": []},
                )
            elif (
                forgery == "read_only_flag"
                and candidate.route_id == "payment.charge"
            ):
                altered = candidate.model_copy(
                    deep=True, update={"read_only": True, "destructive": False},
                )
            else:
                altered = candidate
            rewritten.append(altered)
        return actual.model_copy(update={"candidates": rewritten})

    router.retrieve_authorized = forged_retrieve

    def fail_if_executed(*args, **kwargs):
        raise AssertionError("host contract selection cannot call a tool")

    router.plan = fail_if_executed
    router.execute = fail_if_executed
    if forgery == "hidden_output":
        contract = _contract(
            "wave_height", "ocean_current_velocity", output="sensitive_audit",
        )
    elif forgery == "invented_enum":
        contract = _contract("invented_variable")
    elif forgery == "suppress_competing_match":
        contract = _contract("wave_height")
    else:
        contract = _contract("charged")

    with pytest.raises(
        PolicyViolationError, match="contract differs from current authorized schema",
    ):
        select_authorized_field_contract(
            router, "read published data",
            principal=VIEWER, contract=contract, k=8,
        )


@pytest.mark.parametrize("hidden", (False, True))
def test_field_selection_receipt_uses_original_source_fingerprints(
    hidden: bool,
) -> None:
    """Data-scope field projection never changes the source receipt identity."""
    router = _router(hidden=hidden)
    decision = select_authorized_field_contract(
        router, "marine waves and ocean currents",
        principal=VIEWER,
        contract=_contract(
            "wave_height", "ocean_current_velocity",
            output="ocean_conditions",
        ),
    )
    assert decision.selected_route_id == "marine.read"
    source = router.registry.get("marine")
    assert decision.selected_tool_fingerprint == source.fingerprint
    assert (
        decision.selected_endpoint_fingerprint
        == source.endpoint("read").fingerprint
    )


@pytest.mark.parametrize("field_name", ("tool_fingerprint", "endpoint_fingerprint"))
@pytest.mark.parametrize("target_route", ("marine.read", "archive.read"))
def test_permitted_candidate_cannot_forge_fingerprint_receipt(
    field_name: str,
    target_route: str,
) -> None:
    """Reject any source identity alteration before unique-match authority."""
    router = _router(hidden=True)
    real = router.retrieve_authorized

    def tampered(*args, **kwargs):
        result = real(*args, **kwargs)
        adjusted = [
            candidate.model_copy(
                deep=True, update={field_name: "0" * 64},
            ) if candidate.route_id == target_route else candidate
            for candidate in result.candidates
        ]
        assert any(candidate.route_id == target_route for candidate in adjusted)
        return result.model_copy(update={"candidates": adjusted})

    router.retrieve_authorized = tampered

    def forbid_tool_call(*args, **kwargs):
        raise AssertionError("host field receipt validation must not execute")

    router.plan = forbid_tool_call
    router.execute = forbid_tool_call
    with pytest.raises(
        PolicyViolationError,
        match="fingerprints differ from current authorized source",
    ):
        select_authorized_field_contract(
            router, "marine waves and ocean currents",
            principal=VIEWER,
            contract=_contract(
                "wave_height", "ocean_current_velocity",
                output="ocean_conditions",
            ),
        )


@pytest.mark.asyncio
async def test_async_data_scoped_public_ranked_count_is_pre_top_k() -> None:
    """Async path must not silently turn a truncated K into a total count."""
    from benchmarks.current_adapter_field_scope_dev_v1 import principal
    from benchmarks.current_adapter_scaled_authorized_dev_v1 import build_fixture

    router, _ = build_fixture(100)
    who = principal("viewer")
    first = await router.aretrieve_authorized(
        "read invoice", principal=who, k=3,
    )
    second = await router.aretrieve_authorized(
        "read invoice", principal=who, k=100,
    )
    assert len(first.candidates) == 3
    assert first.total_ranked == second.total_ranked == 95
    assert len(second.candidates) == 95


def test_reprojection_denies_if_visible_route_disappears_mid_scope() -> None:
    """Never return a stale large total if a route becomes hidden after ranking."""
    router = _router(hidden=True)
    original = router.retrieve_authorized(
        "ocean weather", principal=VIEWER, k=3,
    )
    assert len(original.candidates) == 3
    router.authorization_policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="viewer-read", effect="allow", operation="*.*",
                roles_any=("viewer",),
            ),
        ),
        default_effect="deny",
        data_rules=(
            DataScopeRule(
                operation="archive.read", roles_any=("viewer",),
                hidden_fields=("archive_values", "sensitive_audit"),
            ),
        ),
    )
    with pytest.raises(
        PolicyViolationError, match="scope changed during projection",
    ):
        router._project_retrieval_data_scope(original, VIEWER)

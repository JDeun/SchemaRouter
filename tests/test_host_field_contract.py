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
        "read published data", principal=VIEWER, k=3,
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


def test_retrieval_rejects_replaced_policy_after_old_allow_ranking() -> None:
    """An in-flight result cannot inherit a now-revoked permission."""
    router = _router()
    real = router.planner.retrieve_with_additional_availability

    def swap_policy(*args, **kwargs):
        old_allowed = real(*args, **kwargs)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return old_allowed

    router.planner.retrieve_with_additional_availability = swap_policy
    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        router.retrieve_authorized(
            "read ocean conditions", principal=VIEWER, k=3,
        )


def test_scoped_retrieval_rejects_data_policy_replacement_after_ranking() -> None:
    """Replacing field restrictions cannot silently publish an old scope."""
    router = _router(hidden=True)
    real = router.planner.retrieve_with_scoped_schema

    def swap_data_policy(*args, **kwargs):
        old_scoped = real(*args, **kwargs)
        router.authorization_policy = AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    effect="allow", operation="*.*", roles_any=("viewer",),
                ),
            ),
            default_effect="deny",
        )
        return old_scoped

    router.planner.retrieve_with_scoped_schema = swap_data_policy
    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        router.retrieve_authorized(
            "read ocean conditions", principal=VIEWER, k=3,
        )


@pytest.mark.parametrize("mutation", ("registry", "availability"))
def test_retrieval_rejects_changed_authoritative_catalog_mid_request(
    mutation: str,
) -> None:
    """An old route ranking is invalid if the live source definition changes."""
    router = _router()
    real = router.planner.retrieve_with_additional_availability

    def mutate_source(*args, **kwargs):
        result = real(*args, **kwargs)
        if mutation == "registry":
            router.add_tool(ToolSpec(
                name="fresh", description="Fresh current data",
                endpoints=[_endpoint(
                    "read", ["new_value"], output="new_data",
                )],
            ))
        else:
            router.planner.availability_predicate = (
                lambda tool, endpoint: tool.key != "marine"
            )
        return result

    router.planner.retrieve_with_additional_availability = mutate_source
    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        router.retrieve_authorized(
            "read ocean conditions", principal=VIEWER, k=3,
        )


def test_unscoped_retrieval_rejects_policy_installed_mid_request() -> None:
    """Even previously unrestricted retrieval cannot bypass a newly set policy."""
    router = _router()
    router.authorization_policy = None
    real = router.planner.retrieve

    def install_deny(*args, **kwargs):
        result = real(*args, **kwargs)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return result

    router.planner.retrieve = install_deny
    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        router.retrieve("read ocean conditions", k=3)


@pytest.mark.asyncio
async def test_async_retrieval_rejects_policy_swapped_after_await() -> None:
    router = _router()
    real = router.planner.aretrieve_with_additional_availability

    async def swap_after_await(*args, **kwargs):
        result = await real(*args, **kwargs)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return result

    router.planner.aretrieve_with_additional_availability = swap_after_await
    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        await router.aretrieve_authorized(
            "read ocean conditions", principal=VIEWER, k=3,
        )


@pytest.mark.asyncio
async def test_stable_sync_and_async_retrieval_preserve_visible_routes() -> None:
    """The witness adds no authorization permission and invokes no tools."""
    router = _router(hidden=True)

    def fail_if_dispatched(*args, **kwargs):
        raise AssertionError("retrieval must not plan or execute any tool")

    router.plan = fail_if_dispatched
    router.execute = fail_if_dispatched
    synchronous = router.retrieve_authorized(
        "read ocean conditions", principal=VIEWER, k=3,
    )
    asynchronous = await router.aretrieve_authorized(
        "read ocean conditions", principal=VIEWER, k=3,
    )
    assert synchronous.candidates
    assert [c.route_id for c in synchronous.candidates] == [
        c.route_id for c in asynchronous.candidates
    ]
    assert synchronous.total_ranked == asynchronous.total_ranked
    assert all(
        "sensitive_audit" not in {field.name for field in c.output_fields}
        for c in synchronous.candidates
    )


@pytest.mark.parametrize("mutation", (
    "rule_effect", "default_effect", "compiled_rule_index",
    "data_scope", "compiled_data_index",
))
def test_same_object_host_policy_mutation_during_retrieval_is_rejected(mutation):
    """Frozen policy identity must not legitimize stale selected source."""
    router = _router(hidden=True)
    policy = router.authorization_policy
    assert policy is not None
    original_retrieve = router.retrieve_authorized

    def drift(*args, **kwargs):
        result = original_retrieve(*args, **kwargs)
        if mutation == "rule_effect":
            object.__setattr__(policy.rules[-1], "effect", "deny")
        elif mutation == "default_effect":
            object.__setattr__(policy, "default_effect", "allow")
        elif mutation == "compiled_rule_index":
            policy._rule_index.partitions.clear()
        elif mutation == "data_scope":
            object.__setattr__(policy.data_rules[0], "hidden_fields", ())
        else:
            policy._data_rule_index.partitions.clear()
        return result

    router.retrieve_authorized = drift
    with pytest.raises(PolicyViolationError, match="policy changed"):
        select_authorized_field_contract(
            router, "marine wave height", principal=VIEWER,
            contract=_contract("wave_height", "ocean_current_velocity"),
        )


def test_same_object_authorization_drift_during_full_catalog_scan_is_rejected():
    router = _router(hidden=True)
    policy = router.authorization_policy
    assert policy is not None
    original_retrieve = router.retrieve_authorized
    original_view = router._data_scope_endpoint_view
    completed_retrieval = False
    def mark_retrieved(*args, **kwargs):
        nonlocal completed_retrieval
        result = original_retrieve(*args, **kwargs)
        completed_retrieval = True
        return result

    def mutate_while_scanning(*args, **kwargs):
        result = original_view(*args, **kwargs)
        if completed_retrieval:
            object.__setattr__(policy.data_rules[0], "hidden_fields", ())
        return result

    router.retrieve_authorized = mark_retrieved
    router._data_scope_endpoint_view = mutate_while_scanning
    with pytest.raises(PolicyViolationError, match="policy changed"):
        select_authorized_field_contract(
            router, "marine", principal=VIEWER,
            contract=_contract("wave_height", "ocean_current_velocity"),
        )


def test_same_object_index_mutation_during_contract_match_cannot_return_selected(
    monkeypatch,
):
    import schemarouter.host_field_contract as module

    router = _router()
    policy = router.authorization_policy
    assert policy is not None
    original = module._candidate_matches

    def mutate_during_match(candidate, contract, **kwargs):
        valid = original(candidate, contract, **kwargs)
        policy._rule_index.partitions.clear()
        return valid

    monkeypatch.setattr(module, "_candidate_matches", mutate_during_match)
    with pytest.raises(PolicyViolationError, match="policy changed"):
        select_authorized_field_contract(
            router, "marine", principal=VIEWER,
            contract=_contract("wave_height", "ocean_current_velocity"),
        )


def test_corrupted_compiled_policy_index_before_retrieval_fails_closed():
    router = _router()
    policy = router.authorization_policy
    assert policy is not None
    object.__setattr__(policy._rule_index, "partitions", [])
    with pytest.raises(PolicyViolationError, match="cannot attest"):
        select_authorized_field_contract(
            router, "marine", principal=VIEWER,
            contract=_contract("wave_height", "ocean_current_velocity"),
        )


def test_static_policy_still_selects_real_authorized_read_only_contract():
    router = _router(hidden=True)
    decision = select_authorized_field_contract(
        router, "marine waves", principal=VIEWER,
        contract=_contract("wave_height", "ocean_current_velocity"),
    )
    assert decision.disposition == "selected"
    assert decision.selected_route_id == "marine.read"


@pytest.mark.parametrize("exception_type", (RuntimeError, PolicyViolationError))
def test_authorized_retrieval_exception_cannot_disclose_hidden_source_details(
    monkeypatch: pytest.MonkeyPatch, exception_type: type[Exception],
) -> None:
    router = _router(hidden=True)
    secret = "NEVER-ECHO-HIDDEN-ROUTE-AND-FIELD-DETAILS"

    def hostile_retrieval(*_args, **_kwargs):
        raise exception_type(secret)

    monkeypatch.setattr(router, "retrieve_authorized", hostile_retrieval)
    with pytest.raises(PolicyViolationError, match="cannot attest authorized retrieval") as e:
        select_authorized_field_contract(
            router, "ocean", principal=VIEWER, contract=_contract("wave_height"),
        )
    assert secret not in str(e.value)


@pytest.mark.parametrize("exception_type", (RuntimeError, PolicyViolationError))
def test_catalog_projection_exception_cannot_disclose_hidden_source_details(
    monkeypatch: pytest.MonkeyPatch, exception_type: type[Exception],
) -> None:
    router = _router(hidden=True)
    request = "ocean"
    # Use a real, principal-scoped snapshot and exercise failure during the
    # selector's SECOND full-catalog completeness witness, not retrieval.
    authorized = router.retrieve_authorized(request, principal=VIEWER, k=128)
    secret = "NEVER-ECHO-CATALOG-SOURCE-AND-HIDDEN-FIELD"

    monkeypatch.setattr(
        router, "retrieve_authorized", lambda *_args, **_kwargs: authorized,
    )

    def hostile_projection(*_args, **_kwargs):
        raise exception_type(secret)

    monkeypatch.setattr(router, "_data_scope_endpoint_view", hostile_projection)
    with pytest.raises(
        PolicyViolationError, match="cannot validate the complete authorized catalog",
    ) as e:
        select_authorized_field_contract(
            router, request, principal=VIEWER, contract=_contract("wave_height"),
        )
    assert secret not in str(e.value)

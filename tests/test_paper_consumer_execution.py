"""E0: P1-proven original producer → actual separately authorized leaf calls."""
from __future__ import annotations

import pytest
from test_paper_observed_binding import ACTOR, ALIASES, _fixture

from schemarouter import AuthorizationPolicy, AuthorizationRule, PrincipalContext
from schemarouter.errors import (
    PolicyViolationError,
    SchemaValidationError,
    TransientInvocationError,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ALIASES)
async def test_original_producer_and_each_consumer_execute_once_with_observed_id(query):
    """Removing real leaf execution or incorrectly prebinding IDs must fail."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    router, catalog, index, seen = _fixture(allow_consumers=True)
    output = await observe_and_execute_paper_plan(
        router, query, principal=ACTOR, catalog=catalog, index=index,
    )
    assert seen[0] == ("root", {})
    assert len(seen) == 3
    assert {name: args for name, args in seen[1:]} == {
        "fork_status": {"customer_id": "customer-017"},
        "fork_owner": {"customer_id": "customer-017"},
    }
    assert output.producer.data == {"customer_id": "customer-017"}
    assert {result.tool: result.data for result in output.consumers} == {
        "fork_status": {"status": "active"},
        "fork_owner": {"owner": "alice"},
    }
    assert output.plan.status == "ready"
    assert output.executable_authority is False
    assert output.provider_provenance_verified is False
    assert output.independent_e2 is False


@pytest.mark.asyncio
async def test_missing_required_consumer_output_aborts_before_other_leaf():
    """A selected required field cannot silently disappear from real data."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    router, catalog, index, seen = _fixture(
        allow_consumers=True,
        consumer_payloads={"fork_owner": {}, "fork_status": {}},
    )
    with pytest.raises(SchemaValidationError, match="required output"):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert len(seen) == 2
    assert seen[0] == ("root", {})


@pytest.mark.asyncio
async def test_consumer_revokes_another_leaf_and_stops_without_partial_receipt():
    """A mid-run policy change cannot let a later branch use stale authority."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    def revoke_next(router, first_consumer):
        other = "fork_owner" if first_consumer == "fork_status" else "fork_status"
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny", rules=(
                AuthorizationRule(
                    effect="deny", operation=f"{other}.read", roles_any=("reader",),
                ),
                AuthorizationRule(
                    effect="allow", operation="*.read", roles_any=("reader",),
                ),
            ),
        )

    router, catalog, index, seen = _fixture(
        allow_consumers=True, on_consumer=revoke_next,
    )
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen[0] == ("root", {})
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_leaf_transient_failure_has_one_attempt_and_no_other_leaf():
    """Default fallback/retry machinery must not multiply paper calls."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    def transient(router, name):
        raise TransientInvocationError(f"transient {name}")

    router, catalog, index, seen = _fixture(
        allow_consumers=True, on_consumer=transient,
    )
    with pytest.raises(TransientInvocationError):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen[0] == ("root", {})
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_approved_host_parameterized_one_hop_executes_one_leaf_only():
    """Explicit source input is not inferred and does not mint a P1 1:N fork."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    router, catalog, index, seen = _fixture(
        source_parameter=True, single_consumer=True, allow_consumers=True,
    )
    output = await observe_and_execute_paper_plan(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        host_source_arguments={"fork_origin.read": {"external_id": "raw-9"}},
    )
    assert seen == [
        ("root", {"external_id": "raw-9"}),
        ("fork_status", {"customer_id": "customer-017"}),
    ]
    assert len(output.consumers) == 1
    assert output.consumers[0].data == {"status": "active"}


@pytest.mark.asyncio
async def test_source_revokes_leaf_before_consumers_no_leaf_executes():
    """The first actual observation is not authorization for downstream I/O."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    def revoke_after_root(router):
        router.planner.availability_predicate = (
            lambda tool, endpoint: tool.key != "fork_owner"
        )

    router, catalog, index, seen = _fixture(
        allow_consumers=True, on_source=revoke_after_root,
    )
    with pytest.raises(PolicyViolationError):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_unexpected_consumer_result_identity_never_publishes_a_join(monkeypatch):
    """Even a faulty executor adapter cannot mislabel the combined answer."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    router, catalog, index, seen = _fixture(allow_consumers=True)
    actual_execute = router.execute

    async def mislabeled_result(plan, *, config=None):
        result = await actual_execute(plan, config=config)
        if plan.calls[0].tool != "fork_origin":
            return [result[0].model_copy(update={"tool": "not_the_consumer"})]
        return result

    monkeypatch.setattr(router, "execute", mislabeled_result)
    with pytest.raises(SchemaValidationError, match="unexpected tool result"):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen[0] == ("root", {})
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_principal_mutated_during_producer_does_not_execute_leaves():
    """Source tenant A's ID must never run leaves as swapped tenant B."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    principal = PrincipalContext(subject="tenant-a", roles=("reader",))

    def switch_tenant(router):
        principal.subject = "tenant-b"

    router, catalog, index, seen = _fixture(
        allow_consumers=True, on_source=switch_tenant,
    )
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=principal, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_principal_mutated_during_first_leaf_blocks_following_leaf():
    """One valid leaf never authorizes another identity's next request."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    principal = PrincipalContext(subject="tenant-a", roles=("reader",))

    def switch_tenant(router, consumer):
        principal.subject = "tenant-b"

    router, catalog, index, seen = _fixture(
        allow_consumers=True, on_consumer=switch_tenant,
    )
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        await observe_and_execute_paper_plan(
            router, ALIASES[0], principal=principal, catalog=catalog, index=index,
        )
    assert seen[0] == ("root", {})
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_legitimate_nested_consumer_result_paths_preserve_original_output():
    """The executor's declared result_path is evidence, not the field's flat name."""
    from schemarouter.paper_consumer_execution import observe_and_execute_paper_plan

    router, catalog, index, seen = _fixture(
        allow_consumers=True,
        consumer_result_paths={
            "fork_status": ["details", "state"],
            "fork_owner": ["metadata", "owner"],
        },
    )
    output = await observe_and_execute_paper_plan(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
    )
    assert len(seen) == 3
    assert {result.tool: result.data for result in output.consumers} == {
        "fork_status": {"details": {"state": "active"}},
        "fork_owner": {"metadata": {"owner": "alice"}},
    }

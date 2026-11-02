"""Real registered native invoker denial cases for public paper direct SDK.

No monkeypatching of compile, executor, or the registered invoker. The test
records whether a genuinely bound native capability was actually invoked.
"""
from __future__ import annotations

import pytest
from test_research_paper_scoped_agent_real_e0 import CATALOG, QUERY
from test_research_paper_scoped_native_direct_e1 import _fixture

from schemarouter import AuthorizationPolicy, PrincipalContext
from schemarouter.errors import PolicyViolationError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    (
        "missing_host_arguments",
        "denied_principal",
        "unavailable_source",
        "policy_revoked",
    ),
)
async def test_direct_sdk_real_registered_native_denials_never_dispatch(
    case: str,
) -> None:
    """Policy/argument/source denial must happen before any real native call."""
    requires_input = case == "missing_host_arguments"
    view, _index, invoked = _fixture(requires_input=requires_input)
    router = view.router
    session = router.prepare_field_routing(
        catalog=CATALOG,
        approved_host_roots=(
            frozenset({"complete.read"}) if requires_input else frozenset()
        ),
    )
    principal = PrincipalContext(subject="member", roles=("viewer",))
    if case == "denied_principal":
        principal = PrincipalContext(subject="guest", roles=("guest",))
    elif case == "unavailable_source":
        router.mark_access_unavailable("complete", "read", cooldown_seconds=120)
    elif case == "policy_revoked":
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")

    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, principal=principal)
    assert invoked == [], "Rejected native plan must never reach bound provider"


@pytest.mark.asyncio
async def test_direct_sdk_real_registered_native_recovers_from_temporary_unavailability() -> None:
    """Recovery must preserve source-bound argument integrity and never skip policy."""
    view, _index, invoked = _fixture(requires_input=False)
    router = view.router
    session = router.prepare_field_routing(catalog=CATALOG)
    principal = PrincipalContext(subject="member", roles=("viewer",))
    router.mark_access_unavailable("complete", "read", cooldown_seconds=120)

    with pytest.raises(PolicyViolationError):
        await session.aexecute_direct(QUERY, principal=principal)
    assert invoked == []

    router.mark_access_available("complete", "read")
    results = await session.aexecute_direct(QUERY, principal=principal)
    assert invoked == [{}]
    assert len(results) == 1
    assert results[0].tool == "complete"
    assert results[0].data["status"] == "open"


@pytest.mark.asyncio
async def test_direct_sdk_same_contract_binding_generation_drift_never_dispatches() -> None:
    """An invoker swap in a trusted before-call hook is not a removed-tool case.

    The registry and endpoint fingerprints stay identical; only the *bound*
    invoker generation changes after SDK proof but before native invocation.
    """
    from schemarouter.hooks import ExecutionHooks

    view, _index, original_invocations = _fixture(requires_input=False)
    router = view.router
    session = router.prepare_field_routing(catalog=CATALOG)
    principal = PrincipalContext(subject="member", roles=("viewer",))
    replacement_invocations: list[dict] = []
    old = router.executor._binding_snapshot("complete")
    fingerprint = router.registry.get("complete").fingerprint
    assert old.invoker is not None and old.generation is not None

    def replacement(endpoint: str, arguments: dict) -> dict:
        assert endpoint == "read"
        replacement_invocations.append(dict(arguments))
        return {"status": "open", "case_id": "replacement"}

    async def swap_between_validation_and_dispatch(_tool, _endpoint, _call):
        router.executor.bind(
            "complete", replacement, expected_fingerprint=fingerprint,
        )

    router.executor.hooks = ExecutionHooks(before_call=(swap_between_validation_and_dispatch,))
    with pytest.raises(
        PolicyViolationError,
        match="native invoker binding changed during host-pinned execution",
    ):
        await session.aexecute_direct(QUERY, principal=principal)

    assert router.registry.get("complete").fingerprint == fingerprint
    assert router.executor._binding_snapshot("complete").generation != old.generation
    assert original_invocations == []
    assert replacement_invocations == []

    # Without the stale host witness, fresh SDK recompilation is permitted:
    # the unchanged read-only contract can dispatch through the new generation.
    router.executor.hooks = ExecutionHooks()
    result = await session.aexecute_direct(QUERY, principal=principal)
    assert replacement_invocations == [{}]
    assert original_invocations == []
    assert len(result) == 1 and result[0].data["case_id"] == "replacement"

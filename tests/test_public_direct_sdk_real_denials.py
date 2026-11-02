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

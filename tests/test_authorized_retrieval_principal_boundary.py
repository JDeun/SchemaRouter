"""Explicit principal-scoped retrieval must reject invalid Pydantic copies.

Schema integrity is not host authentication. These tests do not authorize
unverified viewer claims or exercise tool execution.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)


def _router() -> SchemaRouter:
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="view-ledger",
                    effect="allow",
                    operation="ledger.read",
                    roles_any=("viewer",),
                ),
            ),
            default_effect="deny",
        ),
    )
    router.add_tool(
        ToolSpec(
            name="ledger",
            description="Read published ledger entries",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description="Read one ledger entry",
                    read_only=True,
                    destructive=False,
                    output_fields=[FieldSpec(name="entry_id")],
                ),
            ],
        )
    )
    return router


def _viewer() -> PrincipalContext:
    return PrincipalContext(
        subject="host-verified-viewer",
        roles=("viewer",),
        attributes={"tenant": "public"},
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"roles": ("viewer", 7)},
        {"roles": ("viewer", "viewer")},
        {"roles": "viewer"},
        {"subject": " "},
        {"attributes": {"tenant": 42}},
        {"departments": ("sales", None)},
    ],
)
def test_sync_rejects_unvalidated_copy_before_lookup(updates: dict) -> None:
    router = _router()
    forged = _viewer().model_copy(update=updates)
    with pytest.raises(PolicyViolationError, match="invalid principal context"):
        router.retrieve_authorized("ledger entry", principal=forged, k=5)
    # Failed explicit lookup must not leak an active principal context.
    with pytest.raises(PolicyViolationError, match="principal context is required"):
        router.retrieve("ledger entry", k=5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "updates",
    [
        {"roles": ("viewer", 7)},
        {"roles": ("viewer", "viewer")},
        {"subject": " "},
        {"attributes": {"tenant": None}},
    ],
)
async def test_async_rejects_unvalidated_copy_before_lookup(updates: dict) -> None:
    router = _router()
    forged = _viewer().model_copy(update=updates)
    with pytest.raises(PolicyViolationError, match="invalid principal context"):
        await router.aretrieve_authorized("ledger entry", principal=forged, k=5)
    with pytest.raises(PolicyViolationError, match="principal context is required"):
        await router.aretrieve("ledger entry", k=5)


@pytest.mark.parametrize("bad", [None, {"roles": ["viewer"]}, "viewer", 7])
def test_sync_rejects_nonprincipal(bad: object) -> None:
    with pytest.raises(PolicyViolationError, match="trusted principal context"):
        _router().retrieve_authorized("ledger entry", principal=bad, k=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, {"roles": ["viewer"]}, "viewer", 7])
async def test_async_rejects_nonprincipal(bad: object) -> None:
    with pytest.raises(PolicyViolationError, match="trusted principal context"):
        await _router().aretrieve_authorized("ledger entry", principal=bad, k=5)


def test_valid_claims_retrieve_readonly_route_but_denied_roles_stay_denied() -> None:
    router = _router()
    approved = router.retrieve_authorized("ledger entry", principal=_viewer(), k=5)
    assert [candidate.route_id for candidate in approved.candidates] == [
        "ledger.read",
    ]
    outsider = PrincipalContext(subject="host-verified-outsider", roles=("outsider",))
    denied = router.retrieve_authorized("ledger entry", principal=outsider, k=5)
    assert denied.candidates == []
    with pytest.raises(PolicyViolationError, match="principal context is required"):
        router.retrieve("ledger entry", k=5)


@pytest.mark.asyncio
async def test_async_valid_claims_retrieve_readonly_route_without_context_leak() -> None:
    router = _router()
    approved = await router.aretrieve_authorized("ledger entry", principal=_viewer(), k=5)
    assert [candidate.route_id for candidate in approved.candidates] == [
        "ledger.read",
    ]
    with pytest.raises(PolicyViolationError, match="principal context is required"):
        await router.aretrieve("ledger entry", k=5)

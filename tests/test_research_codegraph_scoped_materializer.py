"""A selected G5 reference may reveal only revalidated original schemas."""

from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter import DataScopeRule, EndpointSpec, PrincipalContext, ToolSpec
from schemarouter.errors import PolicyViolationError
from scripts.research_codegraph_surgical_context_e0 import _synthetic_control

READER = PrincipalContext(subject="reader-one", roles=("reader",))
QUERY = "case status"


def _episode(*, principal=READER, missing_identifier=False, extra_consumers=0):
    from scripts.research_codegraph_scoped_materializer import capture_surgical_episode

    router, catalog, index = _synthetic_control(
        missing_identifier=missing_identifier, extra_consumers=extra_consumers,
    )
    return router, capture_surgical_episode(
        router, QUERY, principal=principal, catalog=catalog, index=index,
    )


def test_valid_two_route_subset_returns_only_current_original_definitions():
    from scripts.research_codegraph_scoped_materializer import (
        request_scoped_source_schema,
    )

    _, episode = _episode()
    assert episode.public_reference["route_ids"] == ["contacts.read", "cases.read"]
    assert episode.public_reference["tool_call_ready"] is False
    assert "tool_definitions" not in episode.public_reference

    producer_only = request_scoped_source_schema(episode, ["contacts.read"])
    assert [item["name"] for item in producer_only] == ["contacts__read"]
    assert producer_only[0]["parameters"]["additionalProperties"] is False
    both = request_scoped_source_schema(episode, ["contacts.read", "cases.read"])
    assert [item["name"] for item in both] == ["contacts__read", "cases__read"]
    assert both[1]["parameters"]["required"] == ["contact_id", "region_id"]


@pytest.mark.parametrize("requested", (
    [], ["contacts.read", "contacts.read"], ["cases.*"],
    ["unregistered.read"], ["contacts.read", "unregistered.read"],
    ["contacts.read", "cases.read", "other.read", "x.read", "y.read", "z.read"],
))
def test_materializer_rejects_unselected_duplicate_and_wildcard_ids(requested):
    from scripts.research_codegraph_scoped_materializer import (
        request_scoped_source_schema,
    )

    _, episode = _episode()
    with pytest.raises(PolicyViolationError):
        request_scoped_source_schema(episode, requested)


def test_materializer_rejects_in_place_policy_drift():
    from scripts.research_codegraph_scoped_materializer import (
        request_scoped_source_schema,
    )

    router, episode = _episode()
    old = router.authorization_policy
    object.__setattr__(old, "data_rules", (
        DataScopeRule(operation="contacts.read", hidden_fields=("region_id",)),
    ))
    with pytest.raises(PolicyViolationError):
        request_scoped_source_schema(episode, ["contacts.read"])


def test_materializer_rejects_registry_source_and_principal_drift():
    from scripts.research_codegraph_scoped_materializer import (
        request_scoped_source_schema,
    )

    router, episode = _episode()
    router.add_tool(ToolSpec(
        name="other", source_type="crm", license="synthetic-owner-review",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(PolicyViolationError):
        request_scoped_source_schema(episode, ["contacts.read"])

    mutable_principal = PrincipalContext(subject="mutable-reader", roles=("reader",))
    _, mutable_episode = _episode(principal=mutable_principal)
    object.__setattr__(mutable_principal, "roles", ("viewer",))
    with pytest.raises(PolicyViolationError):
        request_scoped_source_schema(mutable_episode, ["contacts.read"])


@pytest.mark.parametrize("variation", ("no_fit", "denied", "over_k"))
def test_no_fit_denied_and_six_route_over_k_have_no_schema_disclosure(variation):
    from scripts.research_codegraph_scoped_materializer import capture_surgical_episode

    router, catalog, index = _synthetic_control(
        missing_identifier=variation == "no_fit",
        extra_consumers=5 if variation == "over_k" else 0,
    )
    principal = (
        PrincipalContext(subject="viewer", roles=("viewer",))
        if variation == "denied" else READER
    )
    with pytest.raises(PolicyViolationError):
        capture_surgical_episode(
            router, QUERY, principal=principal, catalog=catalog, index=index,
        )


def test_hidden_required_producer_field_prevents_disclosure():
    from scripts.research_codegraph_scoped_materializer import (
        request_scoped_source_schema,
    )

    router, episode = _episode()
    original = router.authorization_policy
    assert original is not None
    # A policy replacement with a fresh identity is not silently re-pinned.
    router.authorization_policy = replace(original, data_rules=(
        DataScopeRule(operation="contacts.read", hidden_fields=("contact_id",)),
    ))
    with pytest.raises(PolicyViolationError):
        request_scoped_source_schema(episode, ["cases.read"])

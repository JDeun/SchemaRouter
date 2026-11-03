"""Public owner review preserves only current scoped, declared metadata."""
import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaFieldReviewField,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError

ACTOR = PrincipalContext(subject="reviewer", roles=("reader",))


def _router(field, *, restricted=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="review.read", roles_any=("reader",),
            hidden_fields=("private",),
        ),) if restricted else (),
    ))
    router.add_tool(ToolSpec(
        name="review", source_type="crm", license="declared",
        endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
            field,
            FieldSpec(name="private", aliases=["secret alias"],
                      json_schema={"type": "string"}),
        ])],
    ))
    return router


def _field(**changes):
    values = dict(
        name="public", semantic_id="crm.owner", json_schema={"type": "string"},
        aliases=["account owner", "담당자"],
        qualifiers={"role": "assignee", "channel": "business"},
        path=["payload", "assignee"], result_path=["answer", "owner"],
    )
    values.update(changes)
    return FieldSpec(**values)


def test_review_metadata_is_detached_declared_and_not_concept_authority(monkeypatch):
    router = _router(_field())
    session = router.prepare_field_routing()
    before = router.registry.get("review").model_dump_json()

    def forbidden(*args, **kwargs):
        pytest.fail("review cannot scan private registry inventory or execute providers")

    monkeypatch.setattr(router.registry, "tools", forbidden)
    monkeypatch.setattr(router.registry, "keys", forbidden)
    monkeypatch.setattr(router.executor, "execute", forbidden)
    page = session.inspect_visible_fields(principal=ACTOR)
    item = page.routes[0].fields[0]
    assert item.aliases == ("account owner", "담당자")
    assert item.qualifiers == (("channel", "business"), ("role", "assignee"))
    assert item.source_path == ("payload", "assignee")
    assert item.result_path == ("answer", "owner")
    with pytest.raises(FrozenInstanceError):
        item.aliases = ("invented",)
    with pytest.raises(TypeError):
        item.qualifiers[0][1] = "invented"
    detached = asdict(page)
    detached["routes"][0]["fields"][0]["aliases"] = ("invented",)
    assert "invented" not in repr(page)
    assert router.registry.get("review").model_dump_json() == before
    assert session.inspect_visible_fields(principal=ACTOR) == page
    assert not page.executable_authority
    with pytest.raises(PolicyViolationError, match="catalog"):
        session.compile("account owner", principal=ACTOR)


def test_review_metadata_uses_scoped_redaction_without_recovering_original_paths():
    router = _router(_field(aliases=["secret alias", "safe alias"], qualifiers={
        "role": "secret alias", "safe": "assignee",
    }), restricted=True)
    page = router.prepare_field_routing().inspect_visible_fields(principal=ACTOR)
    item = page.routes[0].fields[0]
    assert item.aliases == item.qualifiers == ()
    assert item.source_path == item.result_path == ("public",)
    assert "secret alias" not in repr(page)
    assert "payload" not in repr(page)
    assert "assignee" not in repr(page)
    # Review redaction does not alter the original execution contract.
    original = router.registry.get("review").endpoints[0].output_fields[0]
    assert original.path == ["payload", "assignee"]
    assert original.qualifiers["role"] == "secret alias"


@pytest.mark.parametrize("metadata", (
    {"aliases": ["가" * 22000]},
    {"qualifiers": {"role": "가" * 22000}},
    {"path": ["가" * 22000]},
    {"result_path": ["가" * 22000]},
    {"aliases": [""] * 24000},
))
def test_review_metadata_cannot_bypass_page_byte_budget(metadata):
    session = _router(_field(**metadata)).prepare_field_routing()
    with pytest.raises(PolicyViolationError, match="budget"):
        session.inspect_visible_fields(principal=ACTOR)


def test_review_metadata_serializes_within_page_cap_and_defaults_are_compatible():
    from schemarouter.field_routing_session import _MAX_REVIEW_PAGE_BYTES

    item = SchemaFieldReviewField("value", "crm.value", "string", None, False)
    assert item.aliases == item.qualifiers == item.source_path == item.result_path == ()
    page = _router(_field(aliases=["가\n\"\\" * 1000])).prepare_field_routing(
    ).inspect_visible_fields(principal=ACTOR)
    encoded = json.dumps(asdict(page), ensure_ascii=True).encode("utf-8")
    assert len(encoded) < _MAX_REVIEW_PAGE_BYTES
    assert b"source_path" in encoded and b"qualifiers" in encoded


@pytest.mark.parametrize("metadata,value", (
    ("aliases", ["changed alias"]),
    ("qualifiers", {"role": "changed role"}),
    ("path", ["changed", "source"]),
    ("result_path", ["changed", "result"]),
))
def test_review_rechecks_live_scoped_metadata_before_releasing_page(
    monkeypatch, metadata, value,
):
    router = _router(_field())
    session = router.prepare_field_routing()
    original = router._data_scope_endpoint_view
    seen = 0

    def changed_scope(principal, tool, endpoint):
        nonlocal seen
        visible = original(principal, tool, endpoint).model_copy(deep=True)
        seen += 1
        if seen >= 2:
            setattr(visible.output_fields[0], metadata, value)
        return visible

    monkeypatch.setattr(router, "_data_scope_endpoint_view", changed_scope)
    with pytest.raises(PolicyViolationError, match="eligibility changed"):
        session.inspect_visible_fields(principal=ACTOR)

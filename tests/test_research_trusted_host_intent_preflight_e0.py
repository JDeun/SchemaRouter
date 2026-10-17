"""Host-authored E0 input preflight: authorization and field safety first."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from schemarouter import SchemaRouter
from schemarouter.authorization import (
    AuthorizationPolicy,
    AuthorizationRule,
    PrincipalContext,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.models import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ToolSpec,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_trusted_host_intent_preflight_e0 import (
    _fits_public_schema,
    preflight_trusted_host_intent_e0,
)

PRINCIPAL = PrincipalContext(subject="dev-reader", roles=("reader",))
SECRET = "PRIVATE-AUTHORIZATION-CANARY-NEVER-PUBLISH"
LANGUAGES = ("en", "ko", "ja")
QUERIES = {
    "en": "Read the marine and papers records",
    "ko": "해양 기록과 문헌 기록을 조회해 주세요",
    "ja": "海洋資料と論文記録を調べてください",
}


def make_router():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="vault.*",
                roles_any=("reader",),
            ),
            AuthorizationRule(
                effect="allow", operation="*.*",
                roles_any=("reader",),
            ),
        ),
    ))
    for name in ("marine", "papers", "vault"):
        router.add_tool(ToolSpec(
            name=name,
            description=f"{name} sample public reader",
            endpoints=[
                EndpointSpec(
                    name="read", description="Read source",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="place", location="query", required=True,
                            json_schema={
                                "type": "string", "minLength": 2,
                                "maxLength": 80,
                            },
                        ),
                        ParameterSpec(
                            name="limit", location="query", required=False,
                            json_schema={
                                "type": "integer", "minimum": 1, "maximum": 10,
                            },
                        ),
                    ],
                    output_fields=[FieldSpec(name="public_count")],
                ),
            ],
        ))
    return router


def capture(router=None, *, query=None):
    router = router or make_router()
    query = query or QUERIES["en"]
    view = capture_authorized_agent_tool_surface(
        router, query, principal=PRINCIPAL,
    )
    assert set(view.visible_route_ids) == {"marine.read", "papers.read"}
    return router, view


def judge(view, hypotheses, arguments=None):
    return preflight_trusted_host_intent_e0(
        view, query=view.original_query,
        host_candidate_routes=hypotheses,
        host_supplied_fields=arguments if arguments is not None else {},
    )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_host_en_ko_ja_hypothesis_separate_from_user_language(lang):
    _, view = capture(query=QUERIES[lang])
    assert judge(view, ("marine.read",), {"place": "Seoul"}).disposition == "ready"
    need = judge(view, ("marine.read",))
    assert need.disposition == "needs_input"
    assert need.protocol == "REQUEST_INPUT"
    vague = judge(view, ("marine.read", "papers.read"), {"place": "Seoul"})
    assert vague.disposition == "ambiguous"
    assert vague.protocol == "CLARIFY_REQUEST"
    for item in (need, vague):
        assert item.executable_authority is False
        assert item.independent_e2_qualified is False
        assert item.model_default_promoted is False


@pytest.mark.parametrize("hypothesis", (
    (), ("vault.read",), ("fictional.read",),
    ("vault.read", "marine.read"),
    ("fictional.read", "marine.read"),
))
def test_hidden_and_unknown_routes_have_same_opaque_disposition(hypothesis):
    _, view = capture()
    result = judge(view, hypothesis, {"place": "Seoul"})
    assert result.disposition == "unavailable"
    assert result.protocol == "REQUEST_MORE_TOOLS"
    data = json.dumps(asdict(result))
    assert "vault" not in data
    assert "fictional" not in data
    assert "marine" not in data
    assert SECRET not in data
    assert result.executable_authority is False


@pytest.mark.parametrize("args", (
    {}, {"place": None}, {"place": ""}, {"place": " "},
    {"place": 100}, {"place": "S"},
    {"place": "Seoul", "limit": "2"},
    {"place": "Seoul", "limit": True},
    {"place": "Seoul", "limit": 0},
    {"place": "Seoul", "limit": 11},
    {"place": "Seoul", "unexpected": "leak"},
))
def test_missing_invalid_and_extra_fields_never_assume_ready(args):
    _, view = capture()
    assert judge(view, ("marine.read",), args).disposition == "needs_input"


def test_optional_typed_fields_are_valid_but_do_not_authorize_execution():
    _, view = capture()
    result = judge(view, ("marine.read",), {"place": "Seoul", "limit": 2})
    assert result.disposition == "ready"
    assert result.protocol is None
    assert result.executable_authority is False
    assert result.real_native_provider_execution is False
    assert result.calibrated_no_fit is False


@pytest.mark.parametrize("bad_routes", (
    ["marine.read"], ("marine.read", "marine.read"),
    ("marine.read", 13), ("marine.read", ""), tuple("abcdefghijk"),
))
def test_host_hypotheses_must_be_unambiguous_typed_bounded(bad_routes):
    _, view = capture()
    with pytest.raises(PolicyViolationError):
        judge(view, bad_routes, {"place": "Seoul"})


@pytest.mark.parametrize("bad_args", (
    {"place": float("nan")}, {"place": object()},
    {"place": "X" * 5000}, {1: "bad"}, [],
))
def test_unverified_or_excessive_host_fields_fail_closed(bad_args):
    _, view = capture()
    with pytest.raises(PolicyViolationError):
        judge(view, ("marine.read",), bad_args)


def test_captured_query_mismatch_does_not_reuse_another_users_authority():
    _, view = capture()
    with pytest.raises(PolicyViolationError, match="query differs"):
        preflight_trusted_host_intent_e0(
            view, query="a different request",
            host_candidate_routes=("marine.read",),
            host_supplied_fields={"place": "Seoul"},
        )


def test_authorized_source_changed_between_capture_and_preflight_fails():
    router, view = capture()
    original = router.authorization_policy
    assert original is not None
    # Frozen policy identity survives a nested object mutation.
    object.__setattr__(original.rules[1], "effect", "deny")
    with pytest.raises(PolicyViolationError, match="policy modified in place"):
        judge(view, ("marine.read",), {"place": "Seoul"})


def test_host_preflight_has_no_model_or_native_provider_side_effects(monkeypatch):
    router, view = capture()
    def never_execute(*args, **kwargs):
        raise AssertionError("preflight must not execute")
    monkeypatch.setattr(router, "execute", never_execute)
    monkeypatch.setattr(router, "run", never_execute)
    assert judge(view, ("marine.read",), {"place": "Seoul"}).disposition == "ready"


@pytest.mark.parametrize(("schema", "value", "expected"), (
    ({"type": "string", "enum": ["Seoul"]}, "Seoul", True),
    ({"type": "string", "enum": ["Seoul"]}, "Busan", False),
    ({"type": "integer", "minimum": 2}, 2, True),
    ({"type": "integer", "minimum": 2}, False, False),
    ({"type": "number", "maximum": 1}, 0.9, True),
    ({"type": "number"}, float("inf"), False),
    ({"type": "boolean"}, True, True),
    ({"type": "boolean"}, 1, False),
    ({"type": "object"}, {"inner": SECRET}, False),
    ({"type": "string", "pattern": ".*"}, "foo", False),
    ({"type": "string", "format": "date"}, "2026", False),
    ({"type": "string", "$ref": "#/secret"}, "foo", False),
))
def test_schema_preflight_never_approves_complex_unvalidated_types(
    schema, value, expected,
):
    assert _fits_public_schema(schema, value) is expected

"""Conjunction must be exact, scope-safe, bounded and abstention-first."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.research_openapi_conjunctive_enum_dev import (
    DEV_REQUIRED_PAIRS,
    select_conjunctive,
    validate_requirement_set,
)


def _candidate(key: str, *, read_only: bool = True,
               vals: tuple[str, ...] = ()):
    return SimpleNamespace(
        route_id=key, read_only=read_only,
        parameters=[SimpleNamespace(
            name="hourly", location="query",
            json_schema={"type": "array", "items": {
                "type": "string", "enum": list(vals),
            }},
        )],
    )


def test_both_marine_fields_needed_and_unique_route_selected() -> None:
    marine = DEV_REQUIRED_PAIRS["marine"]
    assert len(marine) == 2
    rank = ["archive.read", "general.read", "marine.read"]
    options = {
        "archive.read": _candidate("archive.read",
                                   vals=("wave_height",)),
        "general.read": _candidate("general.read",
                                   vals=("ocean_current_velocity",)),
        "marine.read": _candidate("marine.read",
                                  vals=("wave_height",
                                        "ocean_current_velocity")),
    }
    selected, reason, eligible = select_conjunctive(
        rank, options, action="read", requirements=marine,
    )
    assert selected == "marine.read"
    assert reason == "one_exact_conjunction"
    assert eligible == ["marine.read"]


def test_single_field_remains_ambiguous_and_no_top1_fallback() -> None:
    ranking = ["other.read", "marine.read"]
    candidates = {
        key: _candidate(key, vals=("wave_height",))
        for key in ranking
    }
    selected, reason, eligible = select_conjunctive(
        ranking, candidates, action="read",
        requirements=(("hourly", "wave_height"),),
    )
    assert selected is None
    assert reason == "ambiguous_conjunction"
    assert eligible == ranking


def test_partial_conjunction_match_rejected() -> None:
    routes = {"marine.partial": _candidate(
        "marine.partial", vals=("wave_height",),
    )}
    selection, reason, eligible = select_conjunctive(
        list(routes), routes, action="read",
        requirements=DEV_REQUIRED_PAIRS["marine"],
    )
    assert selection is None
    assert reason == "no_full_conjunction"
    assert not eligible


@pytest.mark.parametrize("action", (
    "write", "delete", "purchase", "transfer", "unknown", "",
))
def test_no_read_only_contract_can_authorize_mutation(action: str) -> None:
    routes = {"marine.read": _candidate(
        "marine.read",
        vals=("wave_height", "ocean_current_velocity"),
    )}
    selected, reason, eligible = select_conjunctive(
        list(routes), routes, action=action,
        requirements=DEV_REQUIRED_PAIRS["marine"],
    )
    assert selected is None
    assert reason == "denied_action"
    assert eligible == []


def test_writable_endpoint_cannot_pass_read_request() -> None:
    routes = {"unsafe.write": _candidate(
        "unsafe.write", read_only=False,
        vals=("wave_height", "ocean_current_velocity"),
    )}
    chosen, _, matched = select_conjunctive(
        list(routes), routes, action="read",
        requirements=DEV_REQUIRED_PAIRS["marine"],
    )
    assert chosen is None and matched == []


@pytest.mark.parametrize("req", (
    (), (("hourly", "x"),) * 2,
    (("hourly", "x"),) * 5,
    ((" hourly", "x"),), (("hourly", " x"),),
    ((None, "x"),), (("", "x"),),
    (("hourly", "x" * 129),), ("hourly",),
    ((1, "x"),),
))
def test_invalid_host_contract_fails_closed(req: tuple) -> None:
    with pytest.raises(ValueError):
        validate_requirement_set(req)


def test_no_host_requirement_must_abstain_without_fallback() -> None:
    routes = {"one.read": _candidate("one.read", vals=("wave_height",))}
    chosen, reason, eligible = select_conjunctive(
        list(routes), routes, action="read", requirements=(),
    )
    assert chosen is None and reason == "no_host_requirement"
    assert eligible == []


def test_forged_new_or_duplicate_semantic_ranks_rejected() -> None:
    allowed = {"a.read": _candidate("a.read")}
    for forged in (["a.read", "evil.write"], ["a.read", "a.read"], []):
        with pytest.raises(ValueError, match="authorized"):
            select_conjunctive(
                forged, allowed, action="read",
                requirements=(("hourly", "wave_height"),),
            )


def test_conjunction_requirements_do_not_encode_gold_route() -> None:
    assert DEV_REQUIRED_PAIRS["marine"] == (
        ("hourly", "wave_height"),
        ("hourly", "ocean_current_velocity"),
    )
    assert DEV_REQUIRED_PAIRS["elevation"] == ()
    assert len(DEV_REQUIRED_PAIRS) == 9

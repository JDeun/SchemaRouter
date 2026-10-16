"""Strict read-only typed request variable coverage and negative safety tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.research_openapi_authorized_enum_gate_dev import (
    REQUIREMENTS,
    conservative_selection,
    source_report,
    supports_requested_variable,
)


def _candidate(
    *,
    route: str,
    writable: bool = False,
    parameter: str = "hourly",
    values: tuple[str, ...] = ("wave_height",),
):
    return SimpleNamespace(
        route_id=route,
        read_only=not writable,
        parameters=[SimpleNamespace(
            name=parameter,
            location="query",
            json_schema={"type": "array", "items": {
                "type": "string", "enum": list(values),
            }},
        )],
    )


def test_a_unique_host_field_contract_can_select_late_semantic_candidate() -> None:
    rank = ["unrelated.m", "marine.wave"]
    candidates = {
        "unrelated.m": _candidate(
            route="unrelated.m", values=("temperature_2m",),
        ),
        "marine.wave": _candidate(route="marine.wave"),
    }
    selected, reason, allowed = conservative_selection(
        rank, candidates, action="read",
        requirement=("hourly", "wave_height"),
    )
    assert selected == "marine.wave"
    assert reason == "one_exact_declared_enum"
    assert allowed == ["marine.wave"]


def test_common_weather_field_causes_abstention_not_arbitrary_route() -> None:
    routes = ["weather.hourly", "archive.hourly"]
    candidates = {
        key: _candidate(route=key, values=("temperature_2m",))
        for key in routes
    }
    selected, reason, allowed = conservative_selection(
        routes, candidates, action="read",
        requirement=("hourly", "temperature_2m"),
    )
    assert selected is None
    assert reason == "ambiguous_exact_enum"
    assert allowed == routes


@pytest.mark.parametrize("action", (
    "write", "delete", "create", "transfer", "", "read_write",
))
def test_real_variable_never_authorizes_unsupported_mutation(action: str) -> None:
    item = _candidate(route="forecast.read", values=("temperature_2m",))
    assert not supports_requested_variable(
        item, action=action, parameter="hourly",
        variable="temperature_2m",
    )


def test_even_read_operation_must_be_actually_read_only() -> None:
    write_route = _candidate(route="danger.write", writable=True)
    assert not supports_requested_variable(
        write_route, action="read", parameter="hourly",
        variable="wave_height",
    )


@pytest.mark.parametrize("field", (None, "", "temperature_2m", "waveHeight"))
def test_missing_or_incorrect_declared_enum_fails_closed(field: str | None) -> None:
    item = _candidate(route="marine.wave")
    assert not supports_requested_variable(
        item, action="read", parameter="hourly", variable=field,
    )


def test_duplicate_or_unapproved_model_route_is_rejected() -> None:
    allowed = {
        "a.read": _candidate(route="a.read"),
        "b.read": _candidate(route="b.read"),
    }
    with pytest.raises(ValueError, match="authorized"):
        conservative_selection(
            ["a.read", "evil.write"], allowed,
            action="read", requirement=("hourly", "wave_height"),
        )
    with pytest.raises(ValueError, match="authorized"):
        conservative_selection(
            ["a.read", "a.read"], allowed,
            action="read", requirement=("hourly", "wave_height"),
        )


def test_unrepresented_request_requires_abstention() -> None:
    routes = {"known.read": _candidate(route="known.read")}
    selected, reason, ranked = conservative_selection(
        ["known.read"], routes, action="read", requirement=None,
    )
    assert selected is None
    assert ranked == []
    assert reason == "no_exact_enum_or_denied_operation"
    assert REQUIREMENTS["elevation"] is None


def test_original_model_artifact_requires_fixed_hash(tmp_path) -> None:
    path = tmp_path / "report.json"
    path.write_text('{"model_id":"fake"}')
    with pytest.raises(ValueError, match="bytes drifted"):
        source_report(path)

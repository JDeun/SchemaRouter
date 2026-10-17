"""Local contract tests; official BFCL data/model are loaded in opt-in CI."""
from __future__ import annotations

import hashlib
import json

import pytest

from schemarouter.decisions import CallableDecisionBackend
from scripts.research_bfcl_v4_public_relevance_e1 import (
    _parse_jsonl, _sha1_git_blob, _words, evidence_only_lexical_guard,
    e5_source_choice, host_visible_lexical_choice,
)

RELEVANT = {
    "name": "weather.forecast",
    "description": "Retrieve weather forecasts for an upcoming date",
    "parameters": {"properties": {
        "location": {"description": "City name for weather forecast"},
    }},
}
IRRELEVANT = {
    "name": "math.factorial",
    "description": "Compute the factorial of an integer",
    "parameters": {"properties": {
        "number": {"description": "Given numeric input to factorial"},
    }},
}


def test_git_blob_sha1_is_true_git_object_hash() -> None:
    assert _sha1_git_blob(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    raw = b'{"id":"multiple_0"}\n'
    assert _sha1_git_blob(raw) == hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
    ).hexdigest()


def test_source_frozen_jsonl_rejects_missing_cases_or_poison() -> None:
    good = json.dumps({"id": "multiple_0"}).encode()
    assert _parse_jsonl(good, "multiple", 1)[0]["id"] == "multiple_0"
    for bad in (b"", good + b"\n" + good, b'{"id":"multiple_1"}'):
        with pytest.raises(ValueError):
            _parse_jsonl(bad, "multiple", 1)


def test_existing_schema_router_lexical_retrieval_is_actual_baseline() -> None:
    selected = host_visible_lexical_choice(
        "Weather forecast in Tokyo tomorrow", [RELEVANT, IRRELEVANT],
    )
    assert selected in {RELEVANT["name"], IRRELEVANT["name"]}
    assert selected is not None


def test_unfitted_guard_rejects_obvious_irrelevant_single_tool() -> None:
    assert evidence_only_lexical_guard(
        "Solve the cubic equation for all roots",
        IRRELEVANT["name"], [IRRELEVANT],
    ) is None
    assert len(_words("weather forecast in Tokyo")) >= 2
    assert evidence_only_lexical_guard(
        "Show the weather forecast tomorrow in Tokyo",
        RELEVANT["name"], [RELEVANT],
    ) == RELEVANT["name"]


def test_untrusted_backend_cannot_select_unoffered_function() -> None:
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "visible:999"}]},
    )
    with pytest.raises(Exception):
        e5_source_choice("Weather forecast", [RELEVANT, IRRELEVANT], backend)


def test_model_only_sees_offered_original_function_descriptions_not_gold() -> None:
    observed = []

    def rank_source(request):
        observed.append(request)
        assert request.query == "Weather forecast tomorrow"
        assert [o.label for o in request.options] == [
            RELEVANT["name"], IRRELEVANT["name"],
        ]
        assert request.max_selections == 1
        assert "expected_operation" not in request.model_dump_json()
        assert "ground_truth" not in request.model_dump_json()
        return {"selections": [{"option_id": "visible:0"}]}

    result = e5_source_choice(
        "Weather forecast tomorrow", [RELEVANT, IRRELEVANT],
        CallableDecisionBackend(rank_source),
    )
    assert result == "weather.forecast"
    assert len(observed) == 1

"""No-weights tests for original schema JSON-only tokenizer cost E0."""
from __future__ import annotations

import pytest

from scripts.benchmark_native_fork_fieldgroup_e0 import ALIASES
from scripts.research_g5_multidomain_paired_k5_e0 import build_multidomain_source
from scripts.research_g5_paired_qwen_schema_tokenizer_e0 import (
    SCHEMA_VERSION,
    TOKENIZER_SHA,
    _encode_len,
    _original_public_menu,
    tokenized_same_k5,
)


class StableTokenizer:
    """Deterministic fake only; NOT recorded as real Qwen tokenizer data."""

    def encode(self, text, *, add_special_tokens=True):
        assert add_special_tokens is False
        return list(text.encode("utf-8"))


@pytest.mark.parametrize("scope", [False, True])
def test_schema_tokenizer_uses_same_exact_current_source_and_quality_denominator(scope):
    result = tokenized_same_k5(
        StableTokenizer(), base_routes=500, mixed_scope=scope,
    )
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["tokenizer_revision"] == TOKENIZER_SHA
    assert result["actual_registered_native_routes"] == 512
    assert result["qualified_paired_cases"] == 9
    assert len(result["rows"]) == 9
    assert result["paired_g5_native_json_tokens"] > 0
    assert result["paired_lexical_native_json_tokens"] > 0
    assert result["paired_g5_native_json_tokens"] < result["paired_lexical_native_json_tokens"]
    assert result["model_weights_loaded"] is False
    assert result["original_provider_callbacks"] is False
    assert result["entire_model_prompt_or_completion_tokens_measured"] is False
    assert result["independent_e2_qualified"] is False
    assert result["release_qualified"] is False
    for row in result["rows"]:
        assert row["g5_source_complete"] is True
        assert row["lexical_source_complete"] is True
        assert row["shared_complete_cost_eligible"] is True
        assert row["g5_route_count"] == 3
        assert row["lexical_route_count"] <= 5
        assert row["g5_original_schema_bytes"] > 0
        assert row["lexical_original_schema_bytes"] > 0
        assert len(row["g5_serialized_menu_sha256"]) == 64
        assert len(row["lexical_serialized_menu_sha256"]) == 64


def test_native_menu_is_sorted_current_read_only_provider_and_bytes_match():
    router = build_multidomain_source(500, mixed_scope=True)
    ids = ("fork_status.read", "fork_origin.read", "fork_owner.read")
    text, raw = _original_public_menu(router, ids)
    assert raw == 2050
    assert text.count("\n") == 2
    assert "fork_origin" in text
    assert "fork_status_denied" not in text
    assert "fork_owner_hidden" not in text
    assert "fork_owner" in text
    assert isinstance(ALIASES[0], str)


def test_model_menu_rejects_revoked_native_route_and_missing_source():
    router = build_multidomain_source(500, mixed_scope=True)
    router.planner.availability_predicate = (
        lambda tool, _endpoint: tool.key != "fork_owner"
    )
    with pytest.raises(ValueError, match="unapproved"):
        _original_public_menu(router, ("fork_owner.read",))
    with pytest.raises(Exception):
        _original_public_menu(router, ("unregistered.read",))


@pytest.mark.parametrize("routes", [
    (), ("fork_origin.read", "fork_origin.read"),
    ("fork_origin.read",) * 6,
    ["fork_origin.read"],
    ("noperiod",),
])
def test_invalid_model_menu_denies_unqualified_original_route_sets(routes):
    router = build_multidomain_source(500, mixed_scope=False)
    with pytest.raises(ValueError, match="unqualified"):
        _original_public_menu(router, routes)


@pytest.mark.parametrize("raw", [
    [], [True], [-1], ["bad"], None, (1, -1),
])
def test_invalid_token_receipts_rejected(raw):
    class BadTokenizer:
        def encode(self, text, *, add_special_tokens):
            return raw

    with pytest.raises(ValueError):
        _encode_len(BadTokenizer(), "canonical source")


@pytest.mark.parametrize("base", [True, 0, 499, 501, "500", 500.0])
def test_invalid_synthetic_base_catalog_refused(base):
    with pytest.raises(ValueError, match="pre-registered"):
        tokenized_same_k5(
            StableTokenizer(), base_routes=base, mixed_scope=False,
        )


def test_scoped_original_menu_does_not_expose_hidden_source():
    router = build_multidomain_source(500, mixed_scope=True)
    with pytest.raises(ValueError, match="unapproved|hidden"):
        _original_public_menu(router, ("fork_status_denied.read",))
    with pytest.raises(ValueError, match="unapproved|hidden"):
        _original_public_menu(router, ("fork_owner_hidden.read",))

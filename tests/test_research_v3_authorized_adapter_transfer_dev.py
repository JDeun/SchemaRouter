"""Ensure new local real-parser/auth fixtures do not leak routes via V3 ranking."""
from __future__ import annotations

import pytest

from scripts.research_v3_authorized_adapter_transfer_dev import compare


def test_research_input_must_be_authorized_fixed_top5() -> None:
    for invalid in (0, 3, 10, True):
        with pytest.raises(ValueError):
            compare(k=invalid)


def test_actual_authorized_reranking_never_widens_current_router_visibility() -> None:
    result = compare(k=5)
    assert result["id"] == "frozen_v1_v3_authorized_local_handwritten_DEV"
    assert result["registered_route_count"] == 10
    assert result["two_retrieval_calls_per_case"] == 54
    assert result["width_is_not_distinguishable_on_ten_endpoint_fixture"] is True
    assert len(result["cases"]) == 27
    assert result["overall"]["unauthorized_candidate_count"] == 0
    for row in result["cases"]:
        assert row["v1"]["unauthorized_candidate_count"] == 0
        assert row["v3"]["unauthorized_candidate_count"] == 0
        # No score can count unseen, ineligible or undeclared fields.
        assert set(row["v3"]["required_fields_found"]) <= set(row["required_fields"])
    assert set(result["by_language"]) == {"en", "ko", "ja"}
    assert result["scope"]["actual_current_principal_visibility"] is True
    assert result["scope"]["no_live_provider"] is True
    assert result["scope"]["independent_qualification"] is False
    assert result["scope"]["may_release"] is False

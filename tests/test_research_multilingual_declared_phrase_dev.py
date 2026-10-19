"""E0 self-authored performance and no-fit controls; never publisher E2."""
from __future__ import annotations

import unicodedata

import pytest

from schemarouter.capability_contracts import SemanticEquivalence
from scripts.research_declared_concept_graph_bridge_e0 import (
    DeclaredConceptGraphAnalyzer,
    _matches_declared_phrase,
)
from scripts.research_multilingual_declared_phrase_dev import (
    CASES,
    VIEWER,
    build_router,
    evaluate,
)


def test_scoped_phrase_bridge_improves_supported_korean_japanese_dev() -> None:
    report = evaluate()
    assert report["k"] == 1
    assert report["native_tool_routes"] == 4
    assert report["tool_executions"] == 0
    assert report["independent_confirmation"] is False
    assert report["may_promote"] is False
    assert len(report["rows"]) == len(CASES) == 16
    for lang in ("ko", "ja"):
        before = report["summary"]["exact"][lang]
        after = report["summary"]["bounded_phrase"][lang]
        assert before["positive_evidence_top1_hits"] == 0
        assert after["positive_evidence_top1_hits"] == 3
        assert after["unsupported_positive_evidence"] == 0
    for lang in ("ko", "ja", "en"):
        assert report["summary"]["bounded_phrase"][lang]["unsupported_positive_evidence"] == 0
    for row in report["rows"]:
        for arm in ("exact", "bounded_phrase"):
            assert row["arms"][arm]["latency_ms"] >= 0


@pytest.mark.parametrize(("text", "alias", "expected"), [
    ("탄성계수를 조회", "탄성계수", True),
    ("열전도율 값을 보여줘", "열전도율", True),
    ("ヤング率を教えて", "ヤング率", True),
    ("このヤング率", "ヤング率", True),
    ("Please show Youngs modulus.", "youngs modulus", True),
    ("비탄성계수", "탄성계수", False),
    ("반탄성계수", "탄성계수", False),
    ("unknowns modulus", "youngs modulus", False),
    ("Youngs modulusXYZ", "youngs modulus", False),
    ("탄성계수값", "탄성계수", False),
    ("ラマンピーク測定", "ラマンピーク", False),
    ("unknown", "no", False),
])
def test_bounded_declared_alias_envelope(text: str, alias: str, expected: bool):
    normalized = unicodedata.normalize("NFC", text).casefold()
    assert _matches_declared_phrase(normalized, alias.casefold()) is expected


def test_default_exact_behavior_and_declared_no_invented_translation() -> None:
    exact = build_router("exact")
    proposed = build_router("bounded_phrase")
    query = "탄성계수를 조회해 주세요."
    before = exact.retrieve_authorized(query, principal=VIEWER, k=1)
    after = proposed.retrieve_authorized(query, principal=VIEWER, k=1)
    assert before.candidates[0].score == 0
    assert before.candidates[0].route_id == "a_decoy.read"
    assert after.candidates[0].route_id == "z_mechanics.read"
    assert after.candidates[0].score > 0
    assert all(
        field.name != "private_value"
        for field in after.candidates[0].output_fields
    )
    assert all(
        candidate.tool_fingerprint
        and candidate.endpoint_fingerprint
        for candidate in after.candidates
    )


def test_phrases_with_multiple_semantic_targets_or_explicit_negation_abstain() -> None:
    router = build_router("bounded_phrase")
    for query in (
        "탄성계수 열전도율 둘 다 비교해 주세요.",
        "탄성계수는 제외하고 조회해 주세요.",
        "ヤング率は使わないでください。",
        "Do not use Youngs modulus.",
        "아무 근거 없는 도구를 실행해",
    ):
        retrieval = router.retrieve_authorized(query, principal=VIEWER, k=1)
        assert all(c.score == 0 for c in retrieval.candidates)


def test_original_query_unicode_unmodified_on_opt_in_analysis() -> None:
    router = build_router("bounded_phrase")
    decomposed = unicodedata.normalize("NFD", "탄성계수를 조회해 주세요.")
    assert decomposed != unicodedata.normalize("NFC", decomposed)
    result = router.retrieve_authorized(decomposed, principal=VIEWER, k=1)
    assert result.query == decomposed
    assert result.candidates[0].route_id == "z_mechanics.read"


def test_match_mode_and_ambiguity_are_bounded() -> None:
    with pytest.raises(ValueError, match="match mode"):
        DeclaredConceptGraphAnalyzer((
            SemanticEquivalence(canonical_id="one", aliases={"A"}),
        ), match_mode="unsafe")
    with pytest.raises(ValueError, match="ambiguous"):
        DeclaredConceptGraphAnalyzer((
            SemanticEquivalence(canonical_id="one", aliases={"탄성계수"}),
            SemanticEquivalence(canonical_id="two", aliases={"탄성계수"}),
        ), match_mode="bounded_phrase")

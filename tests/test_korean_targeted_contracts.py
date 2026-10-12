"""Revision-pinned bilingual review of two safety-critical documentation clauses."""

import json
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "audits" / "ko-targeted-contract-review-2026-10-10.json"


def test_targeted_semantic_review_has_live_file_provenance() -> None:
    reviews = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert reviews["schema_version"] == 1
    assert "not independent human sign-off" in reviews["reviewer_status"]
    assert len(reviews["reviews"]) == 2
    for row in reviews["reviews"]:
        assert row["en_blob"] == git_blob_sha(
            (ROOT / "docs" / row["path"]).read_bytes()
        )
        assert row["ko_blob"] == git_blob_sha(
            (ROOT / "docs_ko" / row["path"]).read_bytes()
        )


def test_korean_release_postpublish_verification_matrix_is_explicit() -> None:
    translated = (ROOT / "docs_ko/release-checklist.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "정확히 해당 버전의 PyPI 검증",
        "wheel 및 sdist 설치",
        "MCP/Jev/OpenTelemetry 각각의 독립 extra",
        "MCP/LangChain/LangGraph/LlamaIndex/Jev/OpenTelemetry 결합 extra",
    ):
        assert required in translated


def test_korean_field_unit_contract_is_trusted_and_optional() -> None:
    translated = (
        ROOT / "docs_ko/concepts/field-first-execution.md"
    ).read_text(encoding="utf-8")
    for required in (
        "물리량이나 그 밖에 명시적으로 단위를 갖는 값에만",
        "해당 필드의 계약으로 결정합니다",
        "FieldSpec.semantic_id",
        "의미 식별자가 없을 때만 필드 이름을 사용합니다",
        "모델이 임의로 매핑을 작성하도록 맡기지 않습니다",
        "EvidenceRequirements(units=True)",
    ):
        assert required in translated


def test_direct_semantic_spotcheck_provenance_is_bounded_and_live() -> None:
    ledger = json.loads(
        (ROOT / "audits/ko-direct-semantic-spotcheck-2026-10-12.json").read_text(
            encoding="utf-8"
        )
    )
    assert 16 <= ledger["reviewed_page_pairs"] == len(ledger["reviews"]) <= 147
    assert ledger["total_page_pairs"] == 147
    assert ledger["independent_sentence_review_complete"] is False
    assert "not independent human" in ledger["reviewer_status"]
    assert len({item["path"] for item in ledger["reviews"]}) == len(ledger["reviews"])
    for item in ledger["reviews"]:
        assert item["en_blob"] == git_blob_sha(
            (ROOT / "docs" / item["path"]).read_bytes()
        )
        assert item["ko_blob"] == git_blob_sha(
            (ROOT / "docs_ko" / item["path"]).read_bytes()
        )


def test_korean_laya_documentation_preserves_bounded_decision_semantics() -> None:
    translated = (ROOT / "docs_ko/integrations/laya.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "개발 소스 체크아웃",
        "다음 릴리스가 배포된 뒤",
        "캐시되지 않은 체크포인트 사이를 전환",
        "유효한 옵션 ID를 반환했더라도",
        "신뢰도가 임계값보다 낮은 Laya 선택을 보류",
        "단일 선택을 다중 선택으로 잘못 처리하지 않도록 fail-closed",
        "동일한 코퍼스",
    ):
        assert required in translated


def test_korean_060_openapi_schema_variants_remain_distinct() -> None:
    translated = (ROOT / "docs_ko/releases/0.6.0.md").read_text(
        encoding="utf-8"
    )
    assert "서로 호환되지 않는 스키마 variant를 임의로 평탄화하지 않음" in translated


def test_korean_successor_screen_protects_public_selector_provenance() -> None:
    translated = (ROOT / "docs_ko/research/successor-screen.md").read_text(
        encoding="utf-8"
    )
    assert "비공개(private)" in translated
    assert "순서 규칙을 단위 테스트하는 데에만 사용" in translated
    assert "검증 가능한 provenance" in translated

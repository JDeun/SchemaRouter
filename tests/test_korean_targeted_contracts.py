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

"""Regression checks for two targeted EN/KO protocol contract repairs."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "audits/ko-protocol-ref-and-rpc-review-2026-10-12.json"


def test_review_is_revision_pinned_and_does_not_claim_full_certification() -> None:
    record = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["independent_sentence_review_complete"] is False
    assert "not independent human sign-off" in record["review_status"]
    assert len(record["reviews"]) == 2
    for entry in record["reviews"]:
        assert entry["en_blob"] == git_blob_sha(
            (ROOT / "docs" / entry["path"]).read_bytes()
        )
        assert entry["ko_blob"] == git_blob_sha(
            (ROOT / "docs_ko" / entry["path"]).read_bytes()
        )


def test_cross_document_ref_scope_is_explicit_in_korean() -> None:
    ko = (ROOT / "docs_ko/guides/openapi-compatibility.md").read_text(
        encoding="utf-8"
    )
    assert "별도 문서의 `$ref`를 동일 출처(same-origin) 안에서" in ko
    assert "신뢰된 애플리케이션이 명시적으로 활성화해야 합니다" in ko
    assert "동일한 문서를 가리키는 URI 참조" in ko
    assert "자동으로 로컬 JSON Pointer 참조로 정규화" in ko
    assert "다중 요청·응답 content type" in ko


def test_openrpc_array_item_and_root_projection_are_documented() -> None:
    ko = (ROOT / "docs_ko/guides/openrpc.md").read_text(encoding="utf-8")
    for required in (
        "명시적으로 선언된 array-item field",
        "results[].title",
        "results[].score",
        "원천 레코드의 대응 관계",
        "응답 결과의 루트 자체가 배열이면",
        "가상의 루트 필드명을 만들지 않고",
    ):
        assert required in ko

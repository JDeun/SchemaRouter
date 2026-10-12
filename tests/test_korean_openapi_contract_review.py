"""Guard reviewed OpenAPI EN/KO technical-contract clauses without claiming full parity."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "docs/guides/openapi.md"
KO = ROOT / "docs_ko/guides/openapi.md"
REVIEW = ROOT / "audits/ko-openapi-contract-review-2026-10-12.json"


def test_review_evidence_is_source_pinned_and_limited() -> None:
    record = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["paired_page"] == "guides/openapi.md"
    assert "not independent human sign-off" in record["reviewer_status"]
    assert record["independent_sentence_review_complete"] is False
    assert len(record["reviewed_claims"]) == 4
    assert record["en_blob"] == git_blob_sha(EN.read_bytes())
    assert record["ko_blob"] == git_blob_sha(KO.read_bytes())


def test_openapi_korean_preserves_execution_sensitive_contracts() -> None:
    en = EN.read_text(encoding="utf-8")
    ko = KO.read_text(encoding="utf-8")
    for source_literal in (
        "local reference chains",
        "local Path Item references",
        "schema fingerprint",
        "streamed and capped",
    ):
        assert source_literal in en

    for translated_clause in (
        "로컬 component reference와 이어지는 reference chain",
        "로컬 Path Item reference",
        "schema fingerprint에도 보존합니다",
        "스트리밍 방식으로 읽으며",
        "JSON/text 디코딩 전에",
        "상한을 강제합니다",
        "해당 정보를",
    ):
        assert translated_clause in ko

    # The repair must not alter the mirrored Markdown section hierarchy.
    headings = re.compile(r"^(#{1,6})\\s+", re.MULTILINE)
    assert [len(m.group(1)) for m in headings.finditer(en)] == [
        len(m.group(1)) for m in headings.finditer(ko)
    ]

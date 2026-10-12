"""Exact-blob regression guard for targeted bilingual SDK/OpenRPC/inspection review."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "audits/ko-secondary-contract-review-2026-10-12.json"


def test_targeted_translation_review_has_exact_file_identity() -> None:
    report = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["independent_sentence_review_complete"] is False
    assert "not independent human sign-off" in report["reviewer_status"]
    assert len(report["pairs"]) == 3
    for entry in report["pairs"]:
        en = (ROOT / "docs" / entry["path"]).read_bytes()
        ko = (ROOT / "docs_ko" / entry["path"]).read_bytes()
        assert entry["en_blob"] == git_blob_sha(en)
        assert entry["ko_blob"] == git_blob_sha(ko)
        headings = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
        assert [len(match.group(1)) for match in headings.finditer(en.decode())] == [
            len(match.group(1)) for match in headings.finditer(ko.decode())
        ]


def test_python_invoker_binding_guards_survive_translation() -> None:
    translated = (ROOT / "docs_ko/guides/python-tools.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "정확한 tool fingerprint",
        "compare-and-swap(CAS) 경계",
        "invoker(endpoint_name, arguments)",
        "invoker.invoke_call(tool_call)",
        "신뢰된 전송 상태는 schema에 복사되지 않습니다",
    ):
        assert required in translated


def test_openrpc_array_record_contract_survives_translation() -> None:
    translated = (ROOT / "docs_ko/guides/openrpc.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "results[].title",
        "results[].score",
        "레코드별 필드 대응 관계",
        "인위적인 루트 필드를 만들지 않고",
    ):
        assert required in translated


def test_inspection_commands_have_distinct_korean_meaning() -> None:
    translated = (ROOT / "docs_ko/guides/inspection.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "저장된 전체 실행 기록을 조회합니다",
        "완료 여부에 따라 실행 기록을 필터링합니다",
        "특정 run ID에 해당하는 이벤트 스트림을 검사합니다",
        "--complete",
        "--incomplete",
        "inspect trace <RUN_ID>",
    ):
        assert required in translated

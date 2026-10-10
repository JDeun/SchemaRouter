import json
from pathlib import Path

from scripts.audit_translation_semantic_sections import audit, sections, verify_reviewed
from scripts.prepare_korean_docs import git_blob_sha



def test_section_fence_and_heading() -> None:
    data = (
        "# Main\n\nExplaining the topic.\n\n~~~python\n"
        "# Code fake heading\n~~~\n\n## Details\n\nNever do this."
    )
    result = sections(data)
    assert len(result) == 2
    assert result[0]["heading"] == "Main"


def test_detect_lost_negation_and_heavy_truncation(tmp_path: Path) -> None:
    en = tmp_path / "en"
    ko = tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    text = ("You must not execute remote tools without approval. "
            "Schema drift must not grant new permissions. ") * 6
    (en / "a.md").write_text("# Guide\n\n" + text, encoding="utf-8")
    (ko / "a.md").write_text("# 설명\n\n실행 설명만 있습니다.", encoding="utf-8")
    result = audit(en, ko)
    assert result["paired_pages"] == 1
    assert result["flagged_pages"] == 1
    assert result["flagged_sections"] == 1


def test_preserved_korean_negation_is_not_flagged(tmp_path: Path) -> None:
    en = tmp_path / "en"
    ko = tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text("# Guide\n\nNever do this.", encoding="utf-8")
    (ko / "a.md").write_text("# 설명\n\n이 작업은 허용하지 않습니다.", encoding="utf-8")
    assert audit(en, ko)["flagged_sections"] == 0



def test_korean_negative_forms_are_recognized(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text(
        "# Guide\n\nThe model cannot grant permission or execute a mutation.",
        encoding="utf-8",
    )
    (ko / "a.md").write_text(
        "# 설명\n\n모델에 실행 권한이 없으며 데이터 변경을 허가할 수 없습니다.",
        encoding="utf-8",
    )
    assert audit(en, ko)["flagged_sections"] == 0


def test_stale_review_is_rejected(tmp_path: Path) -> None:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text(
        ("# First\n\n" + "This must not be executed without approval. " * 4),
        encoding="utf-8"
    )
    (ko / "a.md").write_text("# 검증\n\n필요합니다.", encoding="utf-8")
    report = audit(en, ko)
    ledger = tmp_path / "ledger.json"
    entry = {
        "path": "a.md",
        "section": 1,
        "en_blob": git_blob_sha((en / "a.md").read_bytes()),
        "ko_blob": git_blob_sha((ko / "a.md").read_bytes()),
        "decision": "meaning-preserved",
    }
    ledger.write_text(json.dumps({"schema_version": 1, "reviews": [entry]}))
    assert verify_reviewed(report, ledger, en, ko) == []
    (ko / "a.md").write_text("# 검증\n\n이제 달라졌습니다.", encoding="utf-8")
    assert verify_reviewed(audit(en, ko), ledger, en, ko)

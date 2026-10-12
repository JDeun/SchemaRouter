"""Independent EN/KO editorial sign-off verifier: provenance, not a semantic oracle."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_translation_review_units import review_units
from scripts.prepare_korean_docs import git_blob_sha
from scripts.verify_independent_translation_review import verify

EN = "# Safety\n\nDo not grant execution authority.\n\nNever bypass local policy.\n"
KO = "# 안전\n\n실행 권한을 부여하지 않습니다.\n\n로컬 정책을 우회하지 않습니다.\n"


def inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    en, ko = tmp_path / "en", tmp_path / "ko"
    en.mkdir()
    ko.mkdir()
    (en / "a.md").write_text(EN, encoding="utf-8")
    (ko / "a.md").write_text(KO, encoding="utf-8")
    return en, ko, tmp_path / "review.json"


def signed() -> dict:
    en_units, ko_units = review_units(EN), review_units(KO)
    return {
        "schema_version": 1,
        "independent_sentence_review_complete": True,
        "reviewer": {
            "identity": "independent-translator@example.org",
            "date": "2026-10-12",
            "independence_basis": "separate from the primary translation author",
        },
        "pages": [{
            "path": "a.md",
            "en_blob": git_blob_sha(EN.encode()),
            "ko_blob": git_blob_sha(KO.encode()),
            "decisions": [
                {
                    "en_indices": [i],
                    "ko_indices": [i],
                    "en_hashes": [en_units[i - 1]["sha256"]],
                    "ko_hashes": [ko_units[i - 1]["sha256"]],
                    "verdict": "equivalent",
                    "rationale": "Full source and target clause compared, including negation.",
                }
                for i in range(1, 4)
            ],
        }],
    }


def test_complete_evidence_is_source_pinned(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    path.write_text(json.dumps(signed()), encoding="utf-8")
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is True
    assert result["reviewed_pages"] == 1
    assert result["reviewed_en_units"] == result["en_review_units"] == 3
    assert result["reviewed_ko_units"] == result["ko_review_units"] == 3


def test_missing_review_does_not_pass(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is False
    assert result["reviewed_pages"] == 0


def test_post_review_translation_change_invalidates_signoff(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    path.write_text(json.dumps(signed()), encoding="utf-8")
    (ko / "a.md").write_text(KO + "\n새 문단\n", encoding="utf-8")
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is False
    assert any("stale source or Korean blob" in e for e in result["errors"])


def test_skipped_block_is_rejected(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    data = signed()
    data["pages"][0]["decisions"].pop(1)
    path.write_text(json.dumps(data), encoding="utf-8")
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is False
    assert any("missing, repeated or out-of-order" in e for e in result["errors"])


def test_false_completion_flag_is_rejected(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    data = signed()
    data["independent_sentence_review_complete"] = False
    path.write_text(json.dumps(data), encoding="utf-8")
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is False
    assert "no independent full-review attestation" in result["errors"]


def test_changed_block_digest_rejected(tmp_path: Path) -> None:
    en, ko, path = inputs(tmp_path)
    data = signed()
    data["pages"][0]["decisions"][1]["ko_hashes"] = ["0" * 64]
    path.write_text(json.dumps(data), encoding="utf-8")
    result = verify(en, ko, path)
    assert result["review_evidence_complete"] is False
    assert any("stale/incorrect ko block hashes" in e for e in result["errors"])

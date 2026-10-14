"""Verify bilingual #506 terminal evidence and historical evidence boundaries.

These checks are documentation guards only. They do not run, modify, or rescore
the immutable 0.14 source, benchmark tasks, model, or outcome artifacts.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = "38564885951"
ARTIFACT = "11922570109"
ZIP_SHA256 = "c11912ed67a3c02e90c5963ccb462ab44fba3dbd28ced0fe9aacaa92d390eff7"
DETAIL = "research/field-projection-answer-quality.md"
PACKAGE = "research/paper-evidence-package.md"
CHECKPOINT = "research/0.14-paper-evidence-checkpoint.md"


def test_original_projection_confirmation_is_terminal_in_both_languages():
    for root in ("docs", "docs_ko"):
        detail = (ROOT / root / DETAIL).read_text(encoding="utf-8")
        package = (ROOT / root / PACKAGE).read_text(encoding="utf-8")
        checkpoint = (ROOT / root / CHECKPOINT).read_text(encoding="utf-8")
        for page in (detail, package, checkpoint):
            assert RUN in page
            assert ARTIFACT in page
            assert ZIP_SHA256 in page
            assert "#506" in page
        for value in ("1,152", "14.58", "RAW-FULL", "PROJECTED"):
            assert value in detail
        assert "PROJECTED+CONTRACT" in detail
        assert "120/144" in detail or "144개 중 120개" in detail
        assert "#510" in detail
        assert "#1348" in detail


def test_terminal_promotion_is_not_represented_as_factuality_preservation():
    for root in ("docs", "docs_ko"):
        detail = (ROOT / root / DETAIL).read_text(encoding="utf-8")
        assert "unsupported-fact" in detail or "근거 없는 사실" in detail
        assert "30.56%" in detail
        assert "9.52%" in detail
        assert "2026-10-15" in detail

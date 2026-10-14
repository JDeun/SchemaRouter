"""Keep bilingual 0.14 paper evidence synchronized with the canonical outcome.

This is documentation-status verification only, not a scientific evaluator.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUN = "38501112190"
FINAL_RUN = "38506709595"
ZIP_SHA256 = "ac6c4ff2f201ffbc1de4dfd8cfc0a524c79229ad260eb74cfa3a8d2df146f9e7"


def test_bilingual_paper_evidence_package_reports_frozen_negative_result():
    for path in (
        "docs/research/paper-evidence-package.md",
        "docs_ko/research/paper-evidence-package.md",
    ):
        content = (ROOT / path).read_text(encoding="utf-8")
        assert CANONICAL_RUN in content
        assert FINAL_RUN in content
        assert ZIP_SHA256 in content
        for rate in ("49.62%", "29.19%", "31.03%", "25.09%", "70.98%"):
            assert rate in content
        assert "#432 recovery active" not in content
        assert "#432 복구 진행 중" not in content
        assert "#424 대기 중" not in content
        assert "#424 pending" not in content


def test_bilingual_experiment_checkpoint_marks_negative_and_final_pending():
    for path in (
        "docs/research/0.14-paper-evidence-checkpoint.md",
        "docs_ko/research/0.14-paper-evidence-checkpoint.md",
    ):
        content = (ROOT / path).read_text(encoding="utf-8")
        assert CANONICAL_RUN in content
        assert FINAL_RUN in content
        assert "#432" in content and "#424" in content
        assert "no canonical aggregate yet" not in content
        assert "정식 집계 없음" not in content
        assert "38012340016 evaluating" not in content
        assert "#432로 차단" not in content

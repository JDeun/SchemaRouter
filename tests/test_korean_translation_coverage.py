"""Contract tests for the non-blocking Korean translation-depth inventory."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.report_korean_translation_coverage import (
    analyze_pair,
    build_report,
    copied_english_paragraphs,
    markdown_report,
)


class KoreanTranslationCoverageTests(unittest.TestCase):
    def test_verbatim_prose_is_reported_but_code_is_not(self) -> None:
        paragraph = "A substantial English operational rationale and results. " * 9
        code = "```python\n" + ("print('long English snippet')\n" * 20) + "```"
        english = "# Report\n\n" + paragraph + "\n\n" + code + "\n"
        korean = "# 연구\n\n" + paragraph + "\n\n" + code + "\n"
        row = analyze_pair("research.md", english, korean)
        self.assertEqual(row["copied_english_paragraphs"], 1)
        self.assertTrue(row["exact_code_parity"])

    def test_excludes_code_from_copy_detection(self) -> None:
        block = "```text\n" + ("verbatim code documentation example " * 15) + "\n```"
        self.assertEqual(copied_english_paragraphs(block, block), [])

    def test_missing_peer_and_skeletal_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, ko = root / "docs", root / "docs_ko"
            en.mkdir()
            ko.mkdir()
            (en / "full.md").write_text(
                "# Report\n\n" + ("Long reproducible English evidence. " * 65),
                encoding="utf-8",
            )
            (ko / "full.md").write_text("# 보고서\n\n짧은 요약.\n", encoding="utf-8")
            (en / "missing.md").write_text("# Only English", encoding="utf-8")
            result = build_report(en, ko)
            self.assertEqual(result["summary"]["paired_pages"], 1)
            self.assertEqual(result["summary"]["missing_counterparts"], 1)
            self.assertEqual(result["summary"]["skeletal_sections"], 1)
            self.assertIn("missing korean", markdown_report(result))

    def test_links_and_tables_are_audited(self) -> None:
        row = analyze_pair(
            "guide.md",
            "# Guide\n\n[Run](./a.md)\n\n| A |\n| - |",
            "# 안내\n\n[실행](./b.md)\n\n| A |\n| - |",
        )
        self.assertFalse(row["link_target_parity"])
        self.assertTrue(row["table_row_parity"])


if __name__ == "__main__":
    unittest.main()

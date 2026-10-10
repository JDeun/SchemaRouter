"""Prevent rendered H1 corruption from issue IDs at the start of prose."""

from pathlib import Path

from scripts.check_bilingual_docs import unescaped_numeric_issue_references


def test_numeric_issue_id_paragraph_is_rejected(tmp_path: Path) -> None:
    page = tmp_path / "source.md"
    page.write_text(
        "# Actual heading\n"
        "\n"
        "#431 is a GitHub issue, not a heading.\n"
        "- #423 in a list is not an intended heading.\n"
        "이슈 #432는 본문에 포함됩니다.\n"
        "\n"
        "```python\n"
        "#506 comment inside fenced source is allowed\n"
        "```\n",
        encoding="utf-8",
    )
    assert unescaped_numeric_issue_references(page) == [3, 4]


def test_numeric_issue_id_escaped_as_prose_is_allowed(tmp_path: Path) -> None:
    page = tmp_path / "source.md"
    page.write_text(
        "# Actual heading\n\n"
        "Issue #431 is in the body.\n"
        "이슈 #432는 본문에 포함됩니다.\n"
        "\\#506 escaped text also stays in the body.\n",
        encoding="utf-8",
    )
    assert unescaped_numeric_issue_references(page) == []


def test_brand_assets_participate_in_whole_corpus_integrity(tmp_path: Path) -> None:
    from scripts.check_bilingual_docs import markdown_files

    asset = tmp_path / "assets" / "brand" / "README.md"
    asset.parent.mkdir(parents=True)
    asset.write_text("# Brand assets\\n", encoding="utf-8")
    assert "assets/brand/README.md" in markdown_files(tmp_path)


def test_numeric_issue_in_ordered_list_or_quote_is_rejected(tmp_path: Path) -> None:
    page = tmp_path / "ordered.md"
    page.write_text(
        "1. #255 issue reference\\n"
        "2) #256 issue reference\\n"
        "> #262 quoted reference\\n"
        "> 1. #198 nested reference\\n",
        encoding="utf-8",
    )
    assert unescaped_numeric_issue_references(page) == [1, 2, 3, 4]

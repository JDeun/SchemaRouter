#!/usr/bin/env python3
"""Non-gating, reproducible whole-corpus EN/KO coverage audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.audit_korean_translation_coverage import (
    EN,
    KO,
    markdown_files,
    section_prose_lengths,
    structure,
    unchanged_english_prose,
)


def build_report(en_root: Path = EN, ko_root: Path = KO) -> dict[str, object]:
    """Report structural signals without treating length as translation quality."""
    en_files = markdown_files(en_root)
    ko_files = markdown_files(ko_root)
    shared = sorted(en_files.keys() & ko_files.keys())
    pages: list[dict[str, object]] = []

    for rel in shared:
        en_text = en_files[rel].read_text(encoding="utf-8")
        ko_text = ko_files[rel].read_text(encoding="utf-8")
        en_structure = structure(en_files[rel])
        ko_structure = structure(ko_files[rel])
        en_sizes = section_prose_lengths(en_text)
        ko_sizes = section_prose_lengths(ko_text)
        skeletal = (
            sum(
                en >= 650 and ko * 100 < en * 15
                for en, ko in zip(en_sizes, ko_sizes, strict=True)
            )
            if len(en_sizes) == len(ko_sizes)
            else None
        )
        en_bytes = len(en_text.encode("utf-8"))
        ko_bytes = len(ko_text.encode("utf-8"))
        pages.append(
            {
                "path": rel,
                "english_bytes": en_bytes,
                "korean_bytes": ko_bytes,
                "byte_ratio": round(ko_bytes / en_bytes, 4) if en_bytes else None,
                "copied_english_paragraphs": len(
                    unchanged_english_prose(en_text, ko_text)
                ),
                "skeletal_sections": skeletal,
                "heading_levels_match": en_structure[0] == ko_structure[0],
                "code_fence_languages_match": en_structure[1] == ko_structure[1],
                "table_and_admonition_match": (
                    en_structure[2:] == ko_structure[2:]
                ),
            }
        )

    summary = {
        "english_pages": len(en_files),
        "korean_pages": len(ko_files),
        "paired_pages": len(shared),
        "missing_korean_pages": sorted(en_files.keys() - ko_files.keys()),
        "orphan_korean_pages": sorted(ko_files.keys() - en_files.keys()),
        "pages_with_copied_english_paragraphs": sum(
            page["copied_english_paragraphs"] > 0 for page in pages
        ),
        "copied_english_paragraphs": sum(
            int(page["copied_english_paragraphs"]) for page in pages
        ),
        "skeletal_sections": sum(
            int(page["skeletal_sections"] or 0) for page in pages
        ),
        "heading_mismatch_pages": sum(
            not page["heading_levels_match"] for page in pages
        ),
        "code_fence_mismatch_pages": sum(
            not page["code_fence_languages_match"] for page in pages
        ),
        "table_mismatch_pages": sum(
            not page["table_and_admonition_match"] for page in pages
        ),
        "under_half_byte_ratio_pages": sum(
            page["byte_ratio"] is not None and page["byte_ratio"] < 0.5
            for page in pages
        ),
    }
    return {"summary": summary, "pages": pages}


def markdown_summary(report: dict[str, object]) -> str:
    summary = report["summary"]
    pages = report["pages"]
    assert isinstance(summary, dict) and isinstance(pages, list)
    rows = sorted(
        pages,
        key=lambda p: (
            -int(p["copied_english_paragraphs"]),
            -int(p["skeletal_sections"] or 0),
            str(p["path"]),
        ),
    )
    lines = [
        "# SchemaRouter EN/KO documentation audit",
        "",
        "Coverage flags are triage signals, **not** proof of translation quality.",
        "",
        f"- Paired pages: {summary['paired_pages']}",
        f"- Pages with copied English prose: "
        f"{summary['pages_with_copied_english_paragraphs']}",
        f"- Copied long English paragraphs: "
        f"{summary['copied_english_paragraphs']}",
        f"- Skeletal sections: {summary['skeletal_sections']}",
        f"- Heading mismatch pages: {summary['heading_mismatch_pages']}",
        f"- Code-fence mismatch pages: "
        f"{summary['code_fence_mismatch_pages']}",
        f"- Table/admonition mismatch pages: "
        f"{summary['table_mismatch_pages']}",
        f"- Pages below 0.50 KO/EN byte ratio: "
        f"{summary['under_half_byte_ratio_pages']}",
        "",
        "## Prioritized review candidates",
        "",
        "| Page | Copied EN paragraphs | Skeletal sections | KO/EN bytes |",
        "| --- | ---: | ---: | ---: |",
    ]
    for page in rows[:35]:
        ratio = page["byte_ratio"]
        ratio_text = f"{ratio:.2f}" if ratio is not None else "N/A"
        lines.append(
            f"| {page['path']} | {page['copied_english_paragraphs']} | "
            f"{page['skeletal_sections'] or 0} | {ratio_text} |"
        )
    lines.extend(
        [
            "",
            "A copied technical identifier or quoted source is not automatically",
            "a translation defect. Inspect the flagged source sections manually.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_out.write_text(markdown_summary(report), encoding="utf-8")
    print(markdown_summary(report))


if __name__ == "__main__":
    main()

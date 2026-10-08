#!/usr/bin/env python3
"""Report Korean documentation translation gaps without claiming semantic equivalence.

This diagnostic is deliberately non-blocking until the existing translation debt
has been repaired and a reviewed baseline has been established.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"assets/brand/README.md"}
FENCE = re.compile(r"^\s*(`{3,}|~{3,})([^\s`~]*)")
HEADING = re.compile(r"^(#{1,6})\s+")
LINK = re.compile(r"\]\(([^)]+)\)")
TABLE = re.compile(r"^\s*\|.*\|\s*$")
HANGUL = re.compile(r"[가-힣]")
LATIN = re.compile(r"[A-Za-z]")


def markdown_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*.md")
        if p.relative_to(root).as_posix() not in EXCLUDED
    }


def dissect(text: str) -> dict[str, object]:
    """Exclude code fences from prose while retaining the exact code contracts."""
    headings: list[int] = []
    code: list[str] = []
    prose: list[str] = []
    sections: list[int] = []
    table_rows = 0
    active: list[str] | None = None
    marker = ""
    for line in text.splitlines():
        f = FENCE.match(line)
        if active is not None:
            active.append(line)
            if f and f.group(1)[0] == marker:
                code.append("\n".join(active))
                active = None
                marker = ""
            prose.append("")
            continue
        if f:
            active = [line]
            marker = f.group(1)[0]
            prose.append("")
            continue
        prose.append(line)
        heading = HEADING.match(line)
        if heading:
            headings.append(len(heading.group(1)))
            sections.append(0)
        elif sections and not TABLE.match(line):
            sections[-1] += len(line.strip().encode("utf-8"))
        if TABLE.match(line):
            table_rows += 1
    if active is not None:
        code.append("\n".join(active))
    return {
        "headings": headings,
        "code": code,
        "table_rows": table_rows,
        "links": LINK.findall(text),
        "prose": "\n".join(prose),
        "sections": sections,
    }


def copied_english_paragraphs(en_prose: str, ko_prose: str) -> list[str]:
    """Count substantial, verbatim prose. This is a *risk signal*, not MT scoring."""
    target = " ".join(ko_prose.split())
    copied: list[str] = []
    for paragraph in re.split(r"\n\s*\n", en_prose):
        normalized = " ".join(paragraph.split())
        if len(normalized) < 220 or normalized.startswith(("#", "<", "|")):
            continue
        if normalized in target:
            copied.append(normalized)
    return copied


def analyze_pair(path: str, english: str, korean: str) -> dict[str, object]:
    en, ko = dissect(english), dissect(korean)
    en_sections = en["sections"]
    ko_sections = ko["sections"]
    assert isinstance(en_sections, list) and isinstance(ko_sections, list)
    skeletal = []
    if len(en_sections) == len(ko_sections):
        skeletal = [
            index
            for index, (e, k) in enumerate(zip(en_sections, ko_sections, strict=True), 1)
            if e >= 650 and k * 100 < e * 15
        ]
    ko_prose = str(ko["prose"])
    copied = copied_english_paragraphs(str(en["prose"]), ko_prose)
    en_bytes = len(english.encode("utf-8"))
    ko_bytes = len(korean.encode("utf-8"))
    latin = len(LATIN.findall(ko_prose))
    hangul = len(HANGUL.findall(ko_prose))
    return {
        "path": path,
        "english_bytes": en_bytes,
        "korean_bytes": ko_bytes,
        "size_ratio": round(ko_bytes / en_bytes, 4) if en_bytes else None,
        "heading_parity": en["headings"] == ko["headings"],
        "exact_code_parity": en["code"] == ko["code"],
        "table_row_parity": en["table_rows"] == ko["table_rows"],
        "link_target_parity": en["links"] == ko["links"],
        "copied_english_paragraphs": len(copied),
        "skeletal_sections": skeletal,
        "hangul_to_latin_letters": round(hangul / (hangul + latin), 4)
        if hangul + latin else None,
    }


def build_report(english_root: Path, korean_root: Path) -> dict[str, object]:
    english = markdown_files(english_root)
    korean = markdown_files(korean_root)
    paths = sorted(english.keys() | korean.keys())
    rows: list[dict[str, object]] = []
    for rel in paths:
        if rel not in english or rel not in korean:
            rows.append({
                "path": rel,
                "missing": "korean" if rel not in korean else "english",
            })
            continue
        rows.append(analyze_pair(
            rel,
            english[rel].read_text(encoding="utf-8"),
            korean[rel].read_text(encoding="utf-8"),
        ))
    pairs = [r for r in rows if "missing" not in r]
    return {
        "schema_version": 1,
        "summary": {
            "english_pages": len(english),
            "korean_pages": len(korean),
            "paired_pages": len(pairs),
            "missing_counterparts": len(rows) - len(pairs),
            "pages_with_verbatim_english": sum(
                int(r["copied_english_paragraphs"]) > 0 for r in pairs
            ),
            "verbatim_english_paragraphs": sum(
                int(r["copied_english_paragraphs"]) for r in pairs
            ),
            "pages_with_skeletal_sections": sum(
                bool(r["skeletal_sections"]) for r in pairs
            ),
            "skeletal_sections": sum(len(r["skeletal_sections"]) for r in pairs),
            "pages_with_structure_differences": sum(
                any(not r[k] for k in (
                    "heading_parity",
                    "exact_code_parity",
                    "table_row_parity",
                    "link_target_parity",
                )) for r in pairs
            ),
        },
        "pages": rows,
    }


def markdown_report(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    rows = report["pages"]
    assert isinstance(rows, list)
    result = [
        "# Korean documentation translation coverage audit",
        "",
        "This is an actionable **risk inventory**, not a semantic translation score.",
        "Code, hashes, brand/API identifiers and technical English may intentionally remain.",
        "",
    ]
    for key, value in summary.items():
        result.append(f"- {key.replace('_', ' ')}: **{value}**")
    result += [
        "",
        "| Page | Copied EN paragraphs | Skeletal sections | Structure | KO/EN bytes |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    def risk(row: dict[str, object]) -> int:
        if "missing" in row:
            return 10000
        structural = sum(
            not bool(row[k])
            for k in ("heading_parity", "exact_code_parity",
                      "table_row_parity", "link_target_parity")
        )
        return (
            8 * len(row["skeletal_sections"])
            + 4 * int(row["copied_english_paragraphs"])
            + 20 * structural
            + (12 if row["size_ratio"] is not None
               and row["size_ratio"] < 0.5 else 0)
        )
    for row in sorted(rows, key=lambda r: (-risk(r), str(r["path"]))):
        if "missing" in row:
            result.append(f"| `{row['path']}` | — | — | missing {row['missing']} | — |")
            continue
        structure_ok = all(
            bool(row[k]) for k in (
                "heading_parity", "exact_code_parity",
                "table_row_parity", "link_target_parity"
            )
        )
        result.append(
            f"| `{row['path']}` | {row['copied_english_paragraphs']} | "
            f"{len(row['skeletal_sections'])} | "
            f"{'pass' if structure_ok else 'review'} | {row['size_ratio']} |"
        )
    result += [
        "",
        "Byte ratios, copied text and skeletal sections flag review candidates;",
        "they cannot establish translation completeness without semantic review.",
    ]
    return "\n".join(result) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--english-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--korean-root", type=Path, default=ROOT / "docs_ko")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.english_root, args.korean_root)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.markdown_out.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

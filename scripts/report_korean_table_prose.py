#!/usr/bin/env python3
"""Advisory detector for long English prose inside Korean Markdown tables.

This is a localization-risk queue, not an EN/KO semantic-equivalence proof.
Unlike report_korean_english_prose.py, this scan includes Markdown table cells.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?(?:\[[^\]]+\])\([^)]+\)")
WORDS = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)*\b")
KOREAN = re.compile(r"[가-힣]")
FUNCTIONS = frozenset(
    "the and for while where when which was were have has had should must may "
    "cannot not only from before after without then with that those these "
    "there this does did into will their your each both any all are can but "
    "because if it its they is be to of by in on at".split()
)


def candidates(source: str) -> list[dict[str, object]]:
    """Identify likely untranslated prose, not technical identifiers or code."""
    findings: list[dict[str, object]] = []
    fence: str | None = None
    for line_number, line in enumerate(source.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            char = marker.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            continue
        if fence is not None or not line.lstrip().startswith("|"):
            continue
        if re.match(r"^\s*\|\s*:?-{3,}", line):
            continue
        # A Markdown table's backslash-escaped pipe is not a cell separator.
        for cell_index, cell in enumerate(
            re.split(r"(?<!\\)\|", line.strip().strip("|")), 1
        ):
            visible = LINK.sub(" ", INLINE.sub(" ", cell))
            words = WORDS.findall(visible)
            function_words = sum(
                word.lower() in FUNCTIONS for word in words
            )
            if (
                len(words) >= 8
                and function_words >= 2
                and len(KOREAN.findall(visible)) < 6
            ):
                findings.append({
                    "line": line_number,
                    "cell": cell_index,
                    "excerpt": cell.strip()[:220],
                })
    return findings


def scan(root: Path) -> dict[str, object]:
    findings = [
        {"path": path.relative_to(root).as_posix(), **entry}
        for path in sorted(root.rglob("*.md"))
        for entry in candidates(path.read_text(encoding="utf-8"))
    ]
    return {
        "scope": "Table English-prose risk triage only; no semantic certification.",
        "scanned_pages": len(list(root.rglob("*.md"))),
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / "docs_ko")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = scan(args.root)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Scanned {result['scanned_pages']} pages; table prose candidates: "
          f"{len(result['findings'])}")
    for hit in result["findings"]:
        print(f"{hit['path']}:{hit['line']} cell {hit['cell']}: {hit['excerpt']}")
    if args.strict and result["findings"]:
        raise SystemExit("Review untranslated table prose before merging.")


if __name__ == "__main__":
    main()

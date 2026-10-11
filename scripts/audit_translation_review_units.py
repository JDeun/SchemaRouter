#!/usr/bin/env python3
"""Inventory all bilingual Markdown prose blocks; never certify translation quality.

Fenced code belongs to existing code-parity checks. Headings, lists, tables
and normal prose are inventoried, with source line numbers and content hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING = re.compile(r"^\s*#{1,6}\s+")
LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
EN_PROHIBITION = re.compile(
    r"\b(?:must\s+not|may\s+not|should\s+not|cannot|can\s+not|"
    r"do\s+not|does\s+not|never|not\s+allowed|not\s+permitted)\b",
    re.IGNORECASE,
)
KO_PROHIBITION = re.compile(
    r"않|못|없|아니|안\s*됩|금지|거부|차단|불가|제외|허용되지|불허|"
    r"제한|불가능|금해야|해서는\s*안|지\s*마십시오|"
    r"must\s+not|cannot|do\s+not|never|not\s+allowed",
    re.IGNORECASE,
)


def review_units(source: str) -> list[dict[str, object]]:
    """Deterministic Markdown review *blocks*, not inferred sentence pairs."""
    output: list[dict[str, object]] = []
    buffer: list[str] = []
    first_line = 0
    section = 0
    kind = "paragraph"
    fence_char: str | None = None

    def emit(value: str, line: int, block_kind: str) -> None:
        value = value.strip()
        if value:
            output.append({
                "index": len(output) + 1,
                "section": section,
                "line": line,
                "kind": block_kind,
                "text": value,
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            })

    def flush() -> None:
        nonlocal buffer
        if buffer:
            emit("\n".join(buffer), first_line, kind)
            buffer = []

    for lineno, line in enumerate(source.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            char = marker.group(1)[0]
            if fence_char is None:
                flush()
                fence_char = char
            elif fence_char == char:
                fence_char = None
            continue
        if fence_char is not None:
            continue
        if not line.strip():
            flush()
            continue
        if HEADING.match(line):
            flush()
            section += 1
            emit(line, lineno, "heading")
            continue
        new_kind = "table" if line.lstrip().startswith("|") else (
            "list" if LIST_ITEM.match(line) else "paragraph"
        )
        if new_kind in {"table", "list"}:
            flush()
            kind = new_kind
            first_line = lineno
            buffer = [line.rstrip()]
            if new_kind == "table":
                flush()
            continue
        if buffer and kind == "table":
            flush()
        if not buffer:
            first_line = lineno
            kind = "paragraph"
        buffer.append(line.rstrip())
    flush()
    if fence_char is not None:
        raise ValueError("unclosed Markdown fence")
    return output


def audit(en_root: Path, ko_root: Path) -> dict[str, object]:
    en_paths = {p.relative_to(en_root) for p in en_root.rglob("*.md")}
    ko_paths = {p.relative_to(ko_root) for p in ko_root.rglob("*.md")}
    pages: list[dict[str, object]] = []
    risks: list[dict[str, object]] = []
    for rel in sorted(en_paths & ko_paths):
        en = review_units((en_root / rel).read_text(encoding="utf-8"))
        ko = review_units((ko_root / rel).read_text(encoding="utf-8"))
        aligned = len(en) == len(ko) and all(
            x["kind"] == y["kind"] for x, y in zip(en, ko, strict=True)
        )
        # Merged/expanded translated paragraphs cannot be paired by position.
        # A polarity heuristic on a whole section would miss a lost prohibition
        # if some other sentence in that section still contains one.
        if aligned:
            for source, target in zip(en, ko, strict=True):
                if (source["kind"] != "heading"
                        and EN_PROHIBITION.search(str(source["text"]))
                        and not KO_PROHIBITION.search(str(target["text"]))):
                    risks.append({
                        "page": rel.as_posix(), "en_line": source["line"],
                        "ko_line": target["line"], "en_index": source["index"],
                        "signal": "possible missing prohibition in aligned block",
                    })
        pages.append({
            "page": rel.as_posix(), "aligned_by_structure": aligned,
            "en_units": en, "ko_units": ko,
        })
    return {
        "disclaimer": (
            "Advisory review inventory only; no independent bilingual "
            "sentence-by-sentence semantic attestation has been completed."
        ),
        "independent_sentence_review_complete": False,
        "paired_pages": len(pages),
        "missing_korean_pages": sorted(p.as_posix() for p in en_paths - ko_paths),
        "orphan_korean_pages": sorted(p.as_posix() for p in ko_paths - en_paths),
        "structurally_aligned_pages": sum(
            bool(page["aligned_by_structure"]) for page in pages
        ),
        "total_en_units": sum(len(p["en_units"]) for p in pages),
        "total_ko_units": sum(len(p["ko_units"]) for p in pages),
        "advisory_prohibition_risks": risks,
        "pages": pages,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--en-root", type=Path, default=ROOT / "docs")
    p.add_argument("--ko-root", type=Path, default=ROOT / "docs_ko")
    p.add_argument(
        "--json-out", type=Path, default=Path("translation-review-units.json")
    )
    args = p.parse_args()
    report = audit(args.en_root, args.ko_root)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"EN/KO pairs: {report['paired_pages']}; EN blocks: "
          f"{report['total_en_units']}; KO blocks: {report['total_ko_units']}; "
          f"structurally aligned: {report['structurally_aligned_pages']}; "
          f"advisory prohibition risks: {len(report['advisory_prohibition_risks'])}")
    print("Not an independent sentence-level translation certificate.")


if __name__ == "__main__":
    main()

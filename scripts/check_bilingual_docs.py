#!/usr/bin/env python3
"""Fail-closed bilingual documentation integrity checks."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "docs"
KO = ROOT / "docs_ko"
EXCLUDED = {"assets/brand/README.md"}
FENCE = re.compile(r"^\s*(```|~~~)([^\s`]*)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MOJIBAKE = ("\ufffd", "Ã", "Â", "â€™", "â€œ", "â€", "â€“", "â€”", "ðŸ")
PYTHON_SNIPPET = re.compile(r'--8<--\\s+["\\\'][^"\\\']+\\.py(?::[^"\\\']*)?["\\\']')


def markdown_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*.md")
        if p.relative_to(root).as_posix() not in EXCLUDED
    }


def structure(path: Path) -> tuple[list[int], Counter[str], int, int]:
    text = path.read_text(encoding="utf-8")
    headings: list[int] = []
    fences: Counter[str] = Counter()
    tables = 0
    admonitions = 0
    in_fence = False
    for line in text.splitlines():
        match = FENCE.match(line)
        if match:
            marker, language = match.groups()
            if not in_fence:
                fences[language or "<plain>"] += 1
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            headings.append(len(match.group(1)))
        if re.match(r"^\s*\|.*\|\s*$", line):
            tables += 1
        if re.match(r"^\s*!!!\s+", line):
            admonitions += 1
    return headings, fences, tables, admonitions


def unfenced_python_snippets(path: Path) -> list[int]:
    """Return line numbers for Python snippet includes outside code fences."""
    lines: list[int] = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and PYTHON_SNIPPET.search(line):
            lines.append(number)
    return lines


def suspicious_unicode(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [token for token in MOJIBAKE if token in text]


def check_sources() -> list[str]:
    en, ko = markdown_files(EN), markdown_files(KO)
    errors: list[str] = []
    for missing in sorted(set(en) - set(ko)):
        errors.append(f"missing Korean page: {missing}")
    for extra in sorted(set(ko) - set(en)):
        errors.append(f"orphan Korean page: {extra}")
    for rel in sorted(set(en) & set(ko)):
        for label, path in (("EN", en[rel]), ("KO", ko[rel])):
            unsafe = unfenced_python_snippets(path)
            if unsafe:
                errors.append(
                    f"{rel}: {label} Python snippet include outside code fence at lines {unsafe}"
                )
        en_text = en[rel].read_text(encoding="utf-8")
        ko_text = ko[rel].read_text(encoding="utf-8")
        if len(en_text.strip()) > 100 and en_text == ko_text:
            errors.append(f"{rel}: Korean page is byte-identical to English source")
        bad = suspicious_unicode(ko[rel])
        if bad:
            errors.append(f"{rel}: suspicious Unicode/mojibake tokens {bad!r}")
        en_s, ko_s = structure(en[rel]), structure(ko[rel])
        if en_s[0] != ko_s[0]:
            errors.append(
                f"{rel}: heading-level sequence differs EN={en_s[0]} KO={ko_s[0]}"
            )
        if en_s[1] != ko_s[1]:
            errors.append(
                f"{rel}: fenced-code structure differs EN={dict(en_s[1])} KO={dict(ko_s[1])}"
            )
        if en_s[2:] != ko_s[2:]:
            errors.append(
                f"{rel}: table/admonition structure differs EN={en_s[2:]} KO={ko_s[2:]}"
            )
    return errors


def check_rendered(site: Path) -> list[str]:
    errors: list[str] = []
    en_pages = {
        p.relative_to(site)
        for p in site.rglob("*.html")
        if not p.relative_to(site).as_posix().startswith("ko/")
    }
    ko_root = site / "ko"
    ko_pages = {p.relative_to(ko_root) for p in ko_root.rglob("*.html")}
    for rel in sorted(en_pages - ko_pages):
        errors.append(f"rendered Korean page missing: {rel}")
    for rel in sorted(ko_pages - en_pages):
        errors.append(f"rendered Korean page has no English peer: {rel}")
    for rel in sorted(en_pages & ko_pages):
        en_html = (site / rel).read_text(encoding="utf-8")
        ko_html = (ko_root / rel).read_text(encoding="utf-8")
        if 'hreflang="ko"' not in en_html:
            errors.append(f"{rel}: English page lacks ko alternate")
        if 'hreflang="en"' not in ko_html:
            errors.append(f"{rel}: Korean page lacks en alternate")
        if "bilingual-switch.js" not in en_html or "bilingual-switch.js" not in ko_html:
            errors.append(f"{rel}: bilingual route-preserving switch script missing")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path)
    args = parser.parse_args()
    errors = check_sources()
    if args.site:
        errors.extend(check_rendered(args.site))
    if errors:
        message = "bilingual documentation integrity check failed:\n- " + "\n- ".join(errors)
        raise SystemExit(message)
    print("bilingual documentation integrity OK")


if __name__ == "__main__":
    main()

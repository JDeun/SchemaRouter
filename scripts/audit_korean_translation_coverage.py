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
FENCE = re.compile(r"^\s*(```|~~~)([^\s`]*)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MOJIBAKE = ("\ufffd", "Ã", "Â", "â€™", "â€œ", "â€", "â€“", "â€”", "ðŸ")
PYTHON_SNIPPET = re.compile(r'--8<--\\s+["\\\'][^"\\\']+\\.py(?::[^"\\\']*)?["\\\']')


def markdown_files(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*.md")
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


def section_prose_lengths(text: str) -> list[int]:
    """Count non-code, non-heading text in each Markdown heading section."""
    sizes: list[int] = []
    current = -1
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if HEADING.match(line):
            sizes.append(0)
            current += 1
        elif current >= 0:
            sizes[current] += len(line.strip().encode("utf-8"))
    return sizes


def unchanged_english_prose(en_text: str, ko_text: str) -> list[str]:
    """Identify substantial canonical prose copied verbatim into a translation."""
    def without_code(text: str) -> str:
        lines: list[str] = []
        in_fence = False
        for line in text.splitlines():
            if FENCE.match(line):
                in_fence = not in_fence
                lines.append("")
                continue
            lines.append("" if in_fence else line)
        return "\n".join(lines)

    ko_normalized = " ".join(without_code(ko_text).split())
    copies: list[str] = []
    for paragraph in re.split(r"\n\s*\n", without_code(en_text)):
        normalized = " ".join(paragraph.split())
        if len(normalized) < 220 or normalized.startswith(("#", "<", "|")):
            continue
        if normalized in ko_normalized:
            copies.append(normalized)
    return copies


def untranslated_english_prose_lines(text: str) -> list[int]:
    """Advisory triage of substantial English-only Korean-document prose.

    Exclude code fences, link destinations, inline code, tables, and short
    identifier headings. Mixed-language technical prose is *not* judged here;
    neither this heuristic nor a zero count proves semantic equivalence.
    """
    hits: list[int] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        trimmed = line.strip()
        if not trimmed or trimmed.startswith(("|", "<", "http", "!", "    ")):
            continue
        if re.search(r"[\uac00-\ud7a3]", trimmed):
            continue
        cleaned = re.sub(r"`[^`]*`", "", trimmed)
        cleaned = re.sub(r"\]\([^)]*\)", "]", cleaned)
        words = re.findall(r"[A-Za-z]{3,}", cleaned)
        if len(cleaned) >= 36 and len(words) >= 6:
            hits.append(number)
    return hits


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
        copied = unchanged_english_prose(en_text, ko_text)
        if copied:
            errors.append(
                f"{rel}: {len(copied)} substantial English source paragraphs "
                "appear verbatim in Korean; translate explanatory prose"
            )
        # A byte ratio is only a triage signal, not semantic-equivalence proof.
        # A translation shorter than half of a substantial source is a risk.
        en_bytes = len(en_text.encode("utf-8"))
        ko_bytes = len(ko_text.encode("utf-8"))
        if en_bytes >= 2000 and ko_bytes * 2 < en_bytes:
            errors.append(
                f"{rel}: possible severe Korean truncation "
                f"(KO {ko_bytes} bytes / EN {en_bytes} bytes < 0.50); "
                "review section-by-section before merge"
            )
        bad = suspicious_unicode(ko[rel])
        if bad:
            errors.append(f"{rel}: suspicious Unicode/mojibake tokens {bad!r}")
        # Per-section coverage catches skeletal summaries hidden by length padding
        # elsewhere on the page. This threshold is a conservative risk flag.
        en_sections = section_prose_lengths(en_text)
        ko_sections = section_prose_lengths(ko_text)
        if len(en_sections) == len(ko_sections):
            for index, (en_size, ko_size) in enumerate(
                zip(en_sections, ko_sections, strict=True), 1
            ):
                if en_size >= 650 and ko_size * 100 < en_size * 15:
                    errors.append(
                        f"{rel}: section {index} appears skeletal "
                        f"(KO {ko_size} bytes / EN {en_size} bytes); "
                        "review and restore the translated evidence"
                    )
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
        for p in site.rglob("index.html")
        if not p.relative_to(site).as_posix().startswith("ko/")
    }
    ko_root = site / "ko"
    ko_pages = {p.relative_to(ko_root) for p in ko_root.rglob("index.html")}
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

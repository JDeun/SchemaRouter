"""Advisory English/Korean translation meaning-risk triage; never a semantic certificate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^\s*(\x60{3,}|~{3,})")
INLINE = re.compile(r"(?<!\x60)\x60([^\x60\n]{1,180})\x60(?!\x60)")
NUMBER = re.compile(
    r"(?<![A-Za-z0-9_/.#])(\d+(?:[.,]\d+)*)"
    r"(?:\s*(%포인트|%p|pp|percentage points|%|ms|GiB|MiB))?"
    r"(?![A-Za-z0-9_])"
)
EXTERNAL_REFERENCE = re.compile(r"https?://[^\\s)<>\\x60]+")
PROVENANCE = re.compile(r"(?<![A-Za-z0-9_])(?:#[1-9]\d{1,5}|\d{10,12}|[a-f0-9]{40})(?![A-Za-z0-9_])")


def prose(source: str) -> str:
    lines = []
    fence = None
    for line in source.splitlines():
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            lines.append("")
        else:
            lines.append("" if fence is not None else line)
    return "\n".join(lines)


def normalize_number(match: re.Match[str]) -> str:
    magnitude = match.group(1).replace(",", "")
    unit = (match.group(2) or "").strip()
    if unit in {"%p", "%포인트", "percentage points"}:
        unit = "pp"
    return magnitude + unit

def tokens(text: str) -> dict[str, set[str]]:
    visible = prose(text)
    return {
        "technical": {
            match.group(1)
            for match in INLINE.finditer(visible)
            if re.search(r"[._/()\[\]<>=-]", match.group(1))
        },
        "numbers": {normalize_number(match) for match in NUMBER.finditer(visible)},
        "provenance": {match.group(0) for match in PROVENANCE.finditer(visible)},
        "source_links": {match.group(0) for match in EXTERNAL_REFERENCE.finditer(visible)},
    }


def scan(en_root: Path, ko_root: Path) -> dict[str, object]:
    en_paths = {p.relative_to(en_root) for p in en_root.rglob("*.md")}
    ko_paths = {p.relative_to(ko_root) for p in ko_root.rglob("*.md")}
    flags = []
    for path in sorted(en_paths & ko_paths):
        en = tokens((en_root / path).read_text(encoding="utf-8"))
        ko = tokens((ko_root / path).read_text(encoding="utf-8"))
        missing = {kind: sorted(en[kind] - ko[kind]) for kind in en}
        if any(missing.values()):
            flags.append({"page": path.as_posix(), "source_only": missing})
    return {
        "scope": "advisory risk triage, NOT semantic equivalence certification",
        "paired_pages": len(en_paths & ko_paths),
        "flagged_pages": len(flags),
        "flags": flags,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, default=Path("translation-semantic-risks.json"))
    parser.add_argument("--max-show", type=int, default=60)
    args = parser.parse_args()
    result = scan(ROOT / "docs", ROOT / "docs_ko")
    args.json_out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"paired pages: {result['paired_pages']}; flagged pages: {result['flagged_pages']}")
    print("Advisory signals only. Human semantic review is still necessary.")
    for item in result["flags"][:args.max_show]:
        parts = [
            f"{kind}: {len(values)} missing, e.g. {values[:6]}"
            for kind, values in item["source_only"].items()
            if values
        ]
        print(item["page"], "; ".join(parts))


if __name__ == "__main__":
    main()

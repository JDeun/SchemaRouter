#!/usr/bin/env python3
"""Advisory per-section EN/KO meaning-risk report. Not a translation certificate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^\s*(\x60{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.+)")
SENTENCE_NEGATION = re.compile(
    r"\b(?:must not|does not|do not|cannot|can not|never|not allowed|"
    r"fail(?:s)? closed|is not|are not|will not|should not)\b",
    re.IGNORECASE,
)
KOREAN_NEGATION = re.compile(
    r"않|못|없|아닌|금지|거부|차단|실패|불가|안 됩|않습|없이|아니|"
    r"않도|금해야|제외|제한|fail.closed|cannot|does not|not allowed|never",
    re.IGNORECASE,
)


def sections(source: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    in_fence: str | None = None
    for line in source.splitlines():
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if in_fence is None:
                in_fence = marker[0]
            elif marker[0] == in_fence:
                in_fence = None
            continue
        if in_fence is not None:
            continue
        heading = HEADING.match(line)
        if heading:
            result.append(
                {
                    "level": len(heading.group(1)),
                    "heading": heading.group(2),
                    "lines": [],
                }
            )
            continue
        if result and line.strip() and not re.match(r"^\s*\|", line):
            cast = result[-1]["lines"]
            assert isinstance(cast, list)
            cast.append(line.strip())
    return result


def audit(en_root: Path, ko_root: Path) -> dict[str, object]:
    en_files = {p.relative_to(en_root) for p in en_root.rglob("*.md")}
    ko_files = {p.relative_to(ko_root) for p in ko_root.rglob("*.md")}
    findings: list[dict[str, object]] = []
    section_total = 0
    for rel in sorted(en_files & ko_files):
        e = sections((en_root / rel).read_text(encoding="utf-8"))
        k = sections((ko_root / rel).read_text(encoding="utf-8"))
        section_total += len(e)
        if len(e) != len(k):
            findings.append({"path": rel.as_posix(), "error": "heading count differs"})
            continue
        for i, (en, ko) in enumerate(zip(e, k, strict=True), 1):
            en_prose = " ".join(en["lines"])
            ko_prose = " ".join(ko["lines"])
            assert isinstance(en_prose, str) and isinstance(ko_prose, str)
            ratio = len(ko_prose) / max(len(en_prose), 1)
            signals = []
            if len(en_prose) >= 280 and ratio < 0.4:
                signals.append("potential prose omission")
            if (
                len(en_prose) >= 120
                and SENTENCE_NEGATION.search(en_prose)
                and not KOREAN_NEGATION.search(ko_prose)
            ):
                signals.append("negation or fail-closed contract may be lost")
            if signals:
                findings.append(
                    {
                        "path": rel.as_posix(),
                        "section": i,
                        "en_heading": en["heading"],
                        "ko_heading": ko["heading"],
                        "en_chars": len(en_prose),
                        "ko_chars": len(ko_prose),
                        "ratio": round(ratio, 3),
                        "signals": signals,
                        "en_excerpt": en_prose[:450],
                        "ko_excerpt": ko_prose[:450],
                    }
                )
    return {
        "disclaimer": "advisory only: these tests do not prove semantic equivalence",
        "paired_pages": len(en_files & ko_files),
        "sections_compared": section_total,
        "flagged_sections": len(findings),
        "flagged_pages": len({x["path"] for x in findings}),
        "findings": findings,
    }



def verify_reviewed(
    report: dict[str, object],
    ledger_path: Path,
    en_root: Path,
    ko_root: Path,
) -> list[str]:
    """Fail closed on duplicate, malformed, stale or unreviewed risk waivers.

    Every existing waiver is source-pinned even when its previously flagged
    section is no longer selected by the current advisory heuristic.
    """
    review = json.loads(ledger_path.read_text(encoding="utf-8"))
    if review.get("schema_version") != 1 or not isinstance(review.get("reviews"), list):
        return ["invalid semantic editorial ledger schema"]
    approved: dict[tuple[str, int], dict[str, object]] = {}
    seen: set[tuple[str, int]] = set()
    errors: list[str] = []
    for entry in review["reviews"]:
        if not isinstance(entry, dict):
            errors.append("non-object editorial review entry")
            continue
        path, section = entry.get("path"), entry.get("section")
        if (not isinstance(path, str) or not path
                or not isinstance(section, int) or isinstance(section, bool)
                or section <= 0):
            errors.append("invalid editorial path/section identity")
            continue
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".md":
            errors.append(f"unsafe editorial review source path: {path}")
            continue
        key = (path, section)
        if key in seen:
            errors.append(f"{path} section {section}: duplicate editorial disposition")
            continue
        seen.add(key)
        if entry.get("decision") != "meaning-preserved":
            continue
        if not isinstance(entry.get("evidence"), str) or not entry["evidence"].strip():
            errors.append(
                f"{path} section {section}: missing concrete review rationale"
            )
            continue
        valid = True
        for prefix, root in (("en", en_root), ("ko", ko_root)):
            expected = entry.get(f"{prefix}_blob")
            if (not isinstance(expected, str)
                    or not re.fullmatch(r"[0-9a-f]{40}", expected)):
                errors.append(f"{path} section {section}: invalid {prefix} Git blob")
                valid = False
                continue
            candidate = root / pure
            if not candidate.is_file():
                errors.append(f"{path} section {section}: missing {prefix} document")
                valid = False
                continue
            actual = git_blob_sha(candidate.read_bytes())
            if expected != actual:
                errors.append(
                    f"{path} section {section}: {prefix} document changed since review"
                )
                valid = False
        if valid:
            approved[key] = entry
    for item in report["findings"]:
        path, section = item["path"], item.get("section")
        if (path, section) not in approved:
            errors.append(f"{path} section {section}: missing editorial disposition")
    return errors


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--json-out", type=Path, default=Path("translation-section-risks.json")
    )
    p.add_argument("--max-show", type=int, default=70)
    p.add_argument("--review-ledger", type=Path)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    report = audit(ROOT / "docs", ROOT / "docs_ko")
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Advisory semantic-risk triage, NOT proof of per-sentence equivalence.")
    print(
        f"Paired: {report['paired_pages']}; sections: {report['sections_compared']}; "
        f"flagged pages: {report['flagged_pages']}; "
        f"flagged sections: {report['flagged_sections']}"
    )
    if args.strict:
        if not args.review_ledger:
            raise SystemExit("--strict requires --review-ledger")
        problems = verify_reviewed(
            report, args.review_ledger, ROOT / "docs", ROOT / "docs_ko"
        )
        if problems:
            raise SystemExit("unreviewed semantic risk:\n- " + "\n- ".join(problems))
        print("All rule-flagged sections have revision-pinned editorial dispositions.")
    for item in report["findings"][:args.max_show]:
        print(
            f"{item['path']} :: {item.get('section', '?')} "
            f"{item.get('en_heading', '')} "
            f"{item.get('signals', [item.get('error', '')])} "
            f"ratio={item.get('ratio', 'n/a')}"
        )


if __name__ == "__main__":
    main()

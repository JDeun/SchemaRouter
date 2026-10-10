#!/usr/bin/env python3
"""Advisory detection of English prose leakage in Korean Markdown, not semantic certification."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^\s*(\x60{3,}|~{3,})")
INLINE_CODE = re.compile(r"\x60[^\x60\n]*\x60")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]+\]\([^)]*\)")
RAW_URL = re.compile(r"https?://[^\s)]+")
LATIN_WORD = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)*\b")
FUNCTION_WORDS = frozenset(
    "the and for while where when which who was were have has had should must "
    "may cannot not only from before after without then with that those these "
    "there this does did into will their you your each both any all are can but "
    "because if it its they were is be to of by in on at".split()
)


def candidates(source: str) -> list[dict[str, object]]:
    """Ignore technical examples and cited paper titles, not mixed-language prose."""
    findings: list[dict[str, object]] = []
    fence_marker: str | None = None
    for line_number, line in enumerate(source.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            if fence_marker is None:
                fence_marker = marker.group(1)[0]
            elif marker.group(1)[0] == fence_marker:
                fence_marker = None
            continue
        if fence_marker is not None or line.lstrip().startswith(("|", "<!--")):
            continue
        visible = INLINE_CODE.sub(" ", line)
        visible = MARKDOWN_LINK.sub(" ", visible)
        visible = RAW_URL.sub(" ", visible)
        words = LATIN_WORD.findall(visible)
        function_words = [
            word.lower() for word in words if word.lower() in FUNCTION_WORDS
        ]
        if len(words) >= 10 and len(function_words) >= 2:
            findings.append(
                {
                    "line": line_number,
                    "latin_words": len(words),
                    "english_function_words": len(function_words),
                    "excerpt": line[:300],
                }
            )
    return findings


def scan(korean_root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    paths = sorted(korean_root.rglob("*.md"))
    for path in paths:
        for hit in candidates(path.read_text(encoding="utf-8")):
            findings.append({"path": path.relative_to(korean_root).as_posix(), **hit})
    return {
        "scope": (
            "English-prose advisory only; "
            "NOT semantic equivalence or translation certification"
        ),
        "scanned_pages": len(paths),
        "candidate_lines": len(findings),
        "findings": findings,
    }



def verify_reviewed(
    report: dict[str, object], ledger_path: Path, korean_root: Path
) -> list[str]:
    """Fail only on unreviewed/stale English-clause risks, never certify meaning."""
    evidence = json.loads(ledger_path.read_text(encoding="utf-8"))
    if evidence.get("schema_version") != 1 or not isinstance(
        evidence.get("reviews"), list
    ):
        return ["invalid English-prose review ledger"]

    approved: set[tuple[str, int]] = set()
    errors: list[str] = []
    for row in evidence["reviews"]:
        path = row.get("path")
        lines = row.get("lines")
        decision = row.get("decision")
        if not isinstance(path, str) or not isinstance(lines, list):
            errors.append("invalid review path or lines")
            continue
        if not decision or len(lines) == 0:
            errors.append(f"{path}: missing review rationale or line references")
            continue
        file = korean_root / path
        if not file.is_file() or row.get("ko_blob") != git_blob_sha(
            file.read_bytes()
        ):
            errors.append(f"{path}: translation file changed since review")
        for line in lines:
            if not isinstance(line, int) or line <= 0:
                errors.append(f"{path}: invalid reviewed line")
                continue
            key = (path, line)
            if key in approved:
                errors.append(f"{path}:{line}: duplicate reviewed clause")
            approved.add(key)

    findings = report.get("findings")
    if not isinstance(findings, list):
        return errors + ["invalid English-prose scan report"]
    actual = {(str(row["path"]), int(row["line"])) for row in findings}
    for path, line in sorted(actual - approved):
        errors.append(f"{path}:{line}: unreviewed English-prose candidate")
    for path, line in sorted(approved - actual):
        errors.append(f"{path}:{line}: obsolete review disposition")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--korean-root", type=Path, default=ROOT / "docs_ko")
    parser.add_argument(
        "--json-out", type=Path, default=Path("korean-prose-leakage.json")
    )
    parser.add_argument("--max-show", type=int, default=40)
    parser.add_argument("--review-ledger", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = scan(args.korean_root)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Scanned {report['scanned_pages']} pages; "
        f"English prose advisory candidates: {report['candidate_lines']}"
    )
    print("Human review is required; this is NOT a translation certificate.")
    if args.strict:
        if args.review_ledger is None:
            raise SystemExit("--strict requires --review-ledger")
        problems = verify_reviewed(report, args.review_ledger, args.korean_root)
        if problems:
            raise SystemExit("unreviewed English prose:\n- " + "\n- ".join(problems))
        print("All heuristic candidates have revision-pinned dispositions; "
              "semantic fidelity remains unverified.")
    for item in report["findings"][: args.max_show]:
        print(f"{item['path']}:{item['line']}: {item['excerpt']}")


if __name__ == "__main__":
    main()

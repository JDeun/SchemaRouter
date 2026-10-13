#!/usr/bin/env python3
"""Validate independent EN/KO review coverage and provenance, not semantic truth.

No algorithm can infer a truthful reviewer decision from matching hashes.
A completed ledger must be supplied by a separate bilingual reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.audit_translation_review_units import audit
from scripts.prepare_korean_docs import git_blob_sha

ROOT = Path(__file__).resolve().parents[1]
SENTENCE_END = re.compile(r"(?<=[.!?。？！])\s+(?=\S)")


def sentence_hashes(text: str) -> list[str]:
    """Deterministic sentence candidates; human reviewer resolves split ambiguity."""
    return [
        hashlib.sha256(part.strip().encode("utf-8")).hexdigest()
        for part in SENTENCE_END.split(text)
        if part.strip()
    ]


def verify(en_root: Path, ko_root: Path, ledger: Path | None) -> dict[str, object]:
    inventory = audit(en_root, ko_root)
    expected = {p["page"]: p for p in inventory["pages"]}
    errors: list[str] = []
    if inventory["missing_korean_pages"] or inventory["orphan_korean_pages"]:
        errors.append("English/Korean page sets differ")

    if ledger is None or not ledger.is_file():
        data: dict = {}
        errors.append("missing independent reviewer ledger")
    else:
        try:
            parsed = json.loads(ledger.read_text(encoding="utf-8"))
            data = parsed if isinstance(parsed, dict) else {}
        except (ValueError, OSError) as exc:
            data = {}
            errors.append(f"unreadable reviewer ledger: {exc}")
    if data.get("schema_version") != 1:
        errors.append("review ledger schema_version must be 1")
    if data.get("independent_sentence_review_complete") is not True:
        errors.append("no independent full-review attestation")
    reviewer = data.get("reviewer")
    if not isinstance(reviewer, dict) or not all(
        isinstance(reviewer.get(k), str) and reviewer[k].strip()
        for k in ("identity", "date", "independence_basis")
    ):
        errors.append("independent reviewer identity, date and basis are required")

    rows = data.get("pages", [])
    if not isinstance(rows, list):
        rows = []
        errors.append("page reviews must form an array")
    seen: set[str] = set()
    covered_en = covered_ko = 0
    covered_en_sentences = covered_ko_sentences = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append("invalid page review")
            continue
        name = row["path"]
        if name in seen:
            errors.append(f"{name}: duplicate review page")
            continue
        seen.add(name)
        expected_page = expected.get(name)
        if expected_page is None:
            errors.append(f"{name}: not in canonical bilingual corpus")
            continue
        if (row.get("en_blob") != git_blob_sha((en_root / name).read_bytes())
                or row.get("ko_blob") != git_blob_sha((ko_root / name).read_bytes())):
            errors.append(f"{name}: stale source or Korean blob fingerprint")
        decisions = row.get("decisions")
        if not isinstance(decisions, list) or not decisions:
            errors.append(f"{name}: missing reviewed block decisions")
            continue
        en_positions: list[int] = []
        ko_positions: list[int] = []
        for decision in decisions:
            if not isinstance(decision, dict):
                errors.append(f"{name}: invalid block decision")
                continue
            if decision.get("verdict") not in ("equivalent", "corrected"):
                errors.append(f"{name}: verdict must be equivalent or corrected")
            note = decision.get("rationale")
            if not isinstance(note, str) or len(note.strip()) < 16:
                errors.append(f"{name}: independent reviewer rationale missing")
            for lang, positions, units in (
                ("en", en_positions, expected_page["en_units"]),
                ("ko", ko_positions, expected_page["ko_units"]),
            ):
                indices = decision.get(f"{lang}_indices")
                if (not isinstance(indices, list) or not indices
                        or not all(isinstance(x, int) and not isinstance(x, bool)
                                   and x > 0 for x in indices)):
                    errors.append(f"{name}: invalid {lang} indices")
                    continue
                if indices != list(range(indices[0], indices[0] + len(indices))):
                    errors.append(f"{name}: noncontiguous {lang} group")
                positions.extend(indices)
                actual = [units[i-1]["sha256"] for i in indices if i <= len(units)]
                if (len(actual) != len(indices)
                        or actual != decision.get(f"{lang}_hashes")):
                    errors.append(f"{name}: stale/incorrect {lang} block hashes")
                # Block-level certification alone can conceal several sentences.
                sentence_digests = [
                    digest for i in indices if i <= len(units)
                    for digest in sentence_hashes(str(units[i - 1]["text"]))
                ]
                if sentence_digests != decision.get(f"{lang}_sentence_hashes"):
                    errors.append(f"{name}: missing/stale {lang} sentence review hashes")
        for lang, positions, units in (
            ("en", en_positions, expected_page["en_units"]),
            ("ko", ko_positions, expected_page["ko_units"]),
        ):
            if positions != list(range(1, len(units) + 1)):
                errors.append(f"{name}: missing, repeated or out-of-order {lang} blocks")
        valid_en = set(en_positions) & set(range(1, len(expected_page["en_units"]) + 1))
        valid_ko = set(ko_positions) & set(range(1, len(expected_page["ko_units"]) + 1))
        covered_en += len(valid_en)
        covered_ko += len(valid_ko)
        covered_en_sentences += sum(
            len(sentence_hashes(str(expected_page["en_units"][i - 1]["text"])))
            for i in valid_en
        )
        covered_ko_sentences += sum(
            len(sentence_hashes(str(expected_page["ko_units"][i - 1]["text"])))
            for i in valid_ko
        )

    missing = sorted(set(expected) - seen)
    if missing:
        errors.append(f"{len(missing)} unreviewed bilingual page(s)")
    return {
        "scope": (
            "Evidence completeness and hash validity only, not independent "
            "linguistic truth or verified human identity"
        ),
        "paired_pages": inventory["paired_pages"],
        "en_review_units": inventory["total_en_units"],
        "ko_review_units": inventory["total_ko_units"],
        "reviewed_pages": len(seen & set(expected)),
        "reviewed_en_units": covered_en,
        "reviewed_ko_units": covered_ko,
        "en_sentences": sum(
            len(sentence_hashes(str(u["text"])))
            for p in expected.values()
            for u in p["en_units"]
        ),
        "ko_sentences": sum(
            len(sentence_hashes(str(u["text"])))
            for p in expected.values()
            for u in p["ko_units"]
        ),
        "reviewed_en_sentences": covered_en_sentences,
        "reviewed_ko_sentences": covered_ko_sentences,
        "review_evidence_complete": not errors,
        "missing_page_examples": missing[:12],
        "errors": errors[:200],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--ko-root", type=Path, default=ROOT / "docs_ko")
    parser.add_argument("--ledger", type=Path, default=ROOT / "audits/ko-independent-review.json")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    result = verify(args.en_root, args.ko_root, args.ledger)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Independent evidence: {result['reviewed_pages']}/{result['paired_pages']} pages; "
          f"{result['reviewed_en_units']}/{result['en_review_units']} EN blocks; "
          f"{result['reviewed_ko_units']}/{result['ko_review_units']} KO blocks; "
          f"{result['reviewed_en_sentences']}/{result['en_sentences']} EN sentences; "
          f"{result['reviewed_ko_sentences']}/{result['ko_sentences']} KO sentences")
    if result["errors"]:
        print("Outstanding review evidence:", *result["errors"][:12], sep="\n- ")
    if args.require_complete and not result["review_evidence_complete"]:
        raise SystemExit("independent full-corpus review evidence incomplete")


if __name__ == "__main__":
    main()

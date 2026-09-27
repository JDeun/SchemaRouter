"""Audit operation-routing corpora for leakage and structural brittleness.

This tool is diagnostic only. It does not certify a corpus or alter research-cycle
promotion gates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _load(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("corpus must be a JSON case list")
    cases = [case for case in value if isinstance(case, dict)]
    if len(cases) != len(value):
        raise ValueError("every corpus item must be an object")
    return cases


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in _TOKEN_RE.findall(text.casefold())
        if len(token) >= 3
    )


def _normalized(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.casefold())


def _label_token_gaps(
    cases: list[dict[str, Any]],
    *,
    min_docs: int,
    min_rate_gap: float,
) -> list[dict[str, Any]]:
    supported = [case for case in cases if case.get("expected") is not None]
    no_route = [case for case in cases if case.get("expected") is None]
    supported_docs: Counter[str] = Counter()
    no_route_docs: Counter[str] = Counter()

    for case in supported:
        supported_docs.update(_tokens(str(case.get("query", ""))))
    for case in no_route:
        no_route_docs.update(_tokens(str(case.get("query", ""))))

    findings: list[dict[str, Any]] = []
    for token in sorted(set(supported_docs) | set(no_route_docs)):
        support_count = supported_docs[token]
        no_route_count = no_route_docs[token]
        total_docs = support_count + no_route_count
        if total_docs < min_docs:
            continue
        support_rate = support_count / len(supported) if supported else 0.0
        no_route_rate = no_route_count / len(no_route) if no_route else 0.0
        gap = abs(support_rate - no_route_rate)
        if gap < min_rate_gap:
            continue
        findings.append(
            {
                "token": token,
                "supported_docs": support_count,
                "no_route_docs": no_route_count,
                "supported_rate": support_rate,
                "no_route_rate": no_route_rate,
                "absolute_rate_gap": gap,
                "associated_label": (
                    "supported" if support_rate > no_route_rate else "no_route"
                ),
            }
        )
    findings.sort(
        key=lambda item: (
            -float(item["absolute_rate_gap"]),
            -int(item["supported_docs"]) - int(item["no_route_docs"]),
            str(item["token"]),
        )
    )
    return findings


def _near_duplicate_pairs(
    cases: list[dict[str, Any]],
    *,
    threshold: float,
    max_examples: int,
) -> dict[str, Any]:
    by_language: dict[str, list[tuple[str, frozenset[str]]]] = defaultdict(list)
    for case in cases:
        query = str(case.get("query", ""))
        language = str(case.get("language", "unknown"))
        by_language[language].append((str(case.get("id", "")), _tokens(query)))

    pair_count = 0
    examples: list[dict[str, Any]] = []
    for language, rows in sorted(by_language.items()):
        for left_index, (left_id, left_tokens) in enumerate(rows):
            if not left_tokens:
                continue
            for right_id, right_tokens in rows[left_index + 1 :]:
                if not right_tokens:
                    continue
                union = left_tokens | right_tokens
                if not union:
                    continue
                similarity = len(left_tokens & right_tokens) / len(union)
                if similarity < threshold:
                    continue
                pair_count += 1
                if len(examples) < max_examples:
                    examples.append(
                        {
                            "language": language,
                            "left_id": left_id,
                            "right_id": right_id,
                            "token_jaccard": similarity,
                        }
                    )
    return {
        "threshold": threshold,
        "pair_count": pair_count,
        "examples": examples,
    }


def audit(
    cases: list[dict[str, Any]],
    *,
    min_docs: int = 8,
    min_rate_gap: float = 0.20,
    near_duplicate_threshold: float = 0.70,
    max_duplicate_examples: int = 20,
) -> dict[str, Any]:
    ids = [str(case.get("id", "")) for case in cases]
    queries = [str(case.get("query", "")) for case in cases]
    normalized = [_normalized(query) for query in queries]

    language_counts = Counter(str(case.get("language", "unknown")) for case in cases)
    category_counts = Counter(str(case.get("category", "unknown")) for case in cases)
    route_counts = Counter(
        str(case["expected"])
        for case in cases
        if case.get("expected") is not None
    )

    supported_count = sum(case.get("expected") is not None for case in cases)
    no_route_count = len(cases) - supported_count

    return {
        "case_count": len(cases),
        "supported_count": supported_count,
        "no_route_count": no_route_count,
        "duplicate_ids": len(ids) - len(set(ids)),
        "duplicate_normalized_queries": len(normalized) - len(set(normalized)),
        "language_counts": dict(sorted(language_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "supported_route_counts": dict(sorted(route_counts.items())),
        "label_token_gaps": _label_token_gaps(
            cases,
            min_docs=min_docs,
            min_rate_gap=min_rate_gap,
        ),
        "near_duplicates": _near_duplicate_pairs(
            cases,
            threshold=near_duplicate_threshold,
            max_examples=max_duplicate_examples,
        ),
        "interpretation": {
            "label_token_gaps": (
                "High-frequency tokens strongly associated with supported/no-route labels "
                "may indicate label-revealing templates. Review semantically before removal."
            ),
            "near_duplicates": (
                "High token-set overlap can indicate wrapper/template families. A future "
                "blind corpus should hold out semantic/paraphrase families, not only exact text."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--min-docs", type=int, default=8)
    parser.add_argument("--min-rate-gap", type=float, default=0.20)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.70)
    parser.add_argument("--max-duplicate-examples", type=int, default=20)
    args = parser.parse_args()

    if args.min_docs < 1:
        parser.error("--min-docs must be >= 1")
    if not 0.0 <= args.min_rate_gap <= 1.0:
        parser.error("--min-rate-gap must be between 0 and 1")
    if not 0.0 <= args.near_duplicate_threshold <= 1.0:
        parser.error("--near-duplicate-threshold must be between 0 and 1")
    if args.max_duplicate_examples < 0:
        parser.error("--max-duplicate-examples must be >= 0")

    result = audit(
        _load(args.corpus),
        min_docs=args.min_docs,
        min_rate_gap=args.min_rate_gap,
        near_duplicate_threshold=args.near_duplicate_threshold,
        max_duplicate_examples=args.max_duplicate_examples,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

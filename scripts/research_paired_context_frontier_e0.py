"""Paired quality-conditioned schema exposure: existing synthetic routing E0.

Uses the exact preexisting 20–500-route / low-medium-high source and queries,
with a strong schema-aware lexical baseline and the current indexed default
SchemaRouter selector at the SAME K5. Does not instantiate a new graph ranker
or LLM, infer query concepts, or claim G5-native results.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.benchmark_realistic_break_even import (
    AMBIGUITIES,
    SIZES,
    Case,
    _contract_bytes,
    _schema_lexical_documents,
    build_cases,
    build_catalog,
    build_router,
    schema_lexical_select,
    schemarouter_select,
)

MAX_K = 5
SCHEMA = "paired-qualified-schema-exposure-e0-v1"


def _validated_selection(
    selection: list[str], *, registered: frozenset[str],
) -> tuple[str, ...]:
    if (
        type(selection) is not list
        or len(selection) > MAX_K
        or any(type(route) is not str for route in selection)
        or len(set(selection)) != len(selection)
        or not set(selection).issubset(registered)
    ):
        raise ValueError("unsafe / incomparable candidate selection")
    return tuple(selection)


def analyze_paired_cases(
    cases: list[Case],
    lexical: list[list[str]],
    indexed: list[list[str]],
    contract_bytes: dict[str, int],
) -> dict[str, Any]:
    """Compare required route hit and exposure **only** on paired correct hits."""
    if (
        type(cases) is not list or not cases
        or type(lexical) is not list or type(indexed) is not list
        or len(cases) != len(lexical) or len(cases) != len(indexed)
        or type(contract_bytes) is not dict
        or any(
            type(key) is not str or type(value) is not int or value < 0
            for key, value in contract_bytes.items()
        )
        or any(type(case) is not Case for case in cases)
    ):
        raise ValueError("invalid paired E0 cases / source contract budgets")
    registered = frozenset(contract_bytes)
    totals: Counter[str] = Counter()
    bytes_lexical: list[int] = []
    bytes_indexed: list[int] = []
    exposed_lexical: list[int] = []
    exposed_indexed: list[int] = []
    for case, left, right in zip(cases, lexical, indexed, strict=True):
        lex = _validated_selection(left, registered=registered)
        idx = _validated_selection(right, registered=registered)
        totals["cases"] += 1
        totals["supported" if case.supported else "unsupported"] += 1
        exposed_lexical.append(sum(contract_bytes[key] for key in lex))
        exposed_indexed.append(sum(contract_bytes[key] for key in idx))
        if case.supported:
            if type(case.required_tool) is not str or case.required_tool not in registered:
                raise ValueError("invalid required source route in synthetic case")
            lex_hit = case.required_tool in lex
            idx_hit = case.required_tool in idx
            if lex_hit and idx_hit:
                totals["both_hit"] += 1
                lb = sum(contract_bytes[key] for key in lex)
                ib = sum(contract_bytes[key] for key in idx)
                bytes_lexical.append(lb)
                bytes_indexed.append(ib)
                totals["indexed_cheaper_on_paired_hit"] += int(ib < lb)
                totals["lexical_cheaper_on_paired_hit"] += int(lb < ib)
                totals["equal_bytes_on_paired_hit"] += int(lb == ib)
            elif lex_hit:
                totals["lexical_only_hit"] += 1
            elif idx_hit:
                totals["indexed_only_hit"] += 1
            else:
                totals["neither_hit"] += 1
        else:
            if case.required_tool is not None:
                raise ValueError("unsupported synthetic case contains a gold route")
            lex_refused, idx_refused = not lex, not idx
            if lex_refused and idx_refused:
                totals["both_no_fit"] += 1
            elif lex_refused:
                totals["lexical_only_no_fit"] += 1
            elif idx_refused:
                totals["indexed_only_no_fit"] += 1
            else:
                totals["neither_no_fit"] += 1

    correct_lexical = (
        totals["both_hit"] + totals["lexical_only_hit"]
        + totals["both_no_fit"] + totals["lexical_only_no_fit"]
    )
    correct_indexed = (
        totals["both_hit"] + totals["indexed_only_hit"]
        + totals["both_no_fit"] + totals["indexed_only_no_fit"]
    )
    return {
        "case_count": totals["cases"],
        "supported": totals["supported"],
        "unsupported": totals["unsupported"],
        "paired_required_route": {
            name: totals[name] for name in (
                "both_hit", "lexical_only_hit", "indexed_only_hit", "neither_hit",
            )
        },
        "paired_no_fit": {
            name: totals[name] for name in (
                "both_no_fit", "lexical_only_no_fit", "indexed_only_no_fit",
                "neither_no_fit",
            )
        },
        "lexical_case_correct": correct_lexical,
        "indexed_case_correct": correct_indexed,
        "mean_exposed_contract_bytes_all_cases": {
            "schema_lexical_k5": statistics.fmean(exposed_lexical),
            "indexed_default_k5": statistics.fmean(exposed_indexed),
        },
        "quality_conditioned_supported": {
            "both_hit_case_count": len(bytes_lexical),
            "schema_lexical_mean_bytes": (
                statistics.fmean(bytes_lexical) if bytes_lexical else None
            ),
            "indexed_default_mean_bytes": (
                statistics.fmean(bytes_indexed) if bytes_indexed else None
            ),
            "indexed_cheaper_count": totals["indexed_cheaper_on_paired_hit"],
            "lexical_cheaper_count": totals["lexical_cheaper_on_paired_hit"],
            "equal_bytes_count": totals["equal_bytes_on_paired_hit"],
        },
    }


def evaluate(*, sizes: tuple[int, ...] = SIZES) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or any(type(n) is not int or n < 20 or n > 500 for n in sizes)
        or len(set(sizes)) != len(sizes)
    ):
        raise ValueError("frozen benchmark sizes must be distinct and in 20–500")
    matrix: list[dict[str, Any]] = []
    for size in sizes:
        for ambiguity in AMBIGUITIES:
            catalog = build_catalog(size, ambiguity)
            cases = build_cases(size, ambiguity)
            source_bytes = _contract_bytes(catalog)
            registered = frozenset(source_bytes)
            if len(registered) != size:
                raise ValueError("synthetic source IDs not unique")
            lexical_docs = _schema_lexical_documents(catalog)
            router = build_router(catalog, candidate_index=True)
            lexical = [
                schema_lexical_select(case, lexical_docs, k=MAX_K)
                for case in cases
            ]
            indexed = [
                schemarouter_select(router, case, k=MAX_K)
                for case in cases
            ]
            metrics = analyze_paired_cases(cases, lexical, indexed, source_bytes)
            matrix.append({
                "catalog_size": size,
                "ambiguity": ambiguity,
                "full_catalog_contract_bytes": sum(source_bytes.values()),
                **metrics,
            })
    return {
        "schema_version": SCHEMA,
        "evidence_tier": "E0_DEVELOPER_AUTHORED_SYNTHETIC",
        "study": "quality-conditioned native contract exposure against strong lexical",
        "k": MAX_K,
        "methods": ["schema_lexical_k5", "indexed_default_k5"],
        "default_indexed_is_g5_graph": False,
        "all_model_tokens_measured": False,
        "source_disjoint_external_e2_qualified": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
        "matrix": matrix,
        "limitations": [
            "Developer-authored frozen synthetic catalog and query semantics",
            "Schema-aware lexical baseline gets declared field demand from same fixture",
            "Current indexed default is lexical+typed planner, not opt-in G5 graph lookup",
            "Required-route recall is NOT parameter/field-set or agent final accuracy",
            "Serialized contract bytes are NOT tokenizer-measured LLM input tokens",
            "Cost comparison counts only supported cases BOTH methods retrieve correctly",
            "Do not generalize to external publishers or multilingual English-only metadata",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "matrix_cells": len(report["matrix"]),
        "total_developer_cases": sum(row["case_count"] for row in report["matrix"]),
        "independent_e2_qualified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

"""Synthetic catalog-size stress preflight (zero model downloads)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.evaluate_multilingual_embedding_scale_dev import (
    SEED,
    SIZES,
    catalog_hash,
    check_corpus,
    expand_catalog,
)

CORPUS = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/multilingual-embedding-cpu-dev-20261015.json"
)


def test_nested_sizes_keep_all_13_supported_routes_and_exact_counts() -> None:
    corpus, _ = load_development_corpus(CORPUS)
    check_corpus(corpus)
    catalogs = [expand_catalog(corpus["catalog"], size) for size in SIZES]
    assert [len(x) for x in catalogs] == [13, 100, 250, 500]
    for a, b in zip(catalogs, catalogs[1:], strict=False):
        assert a == b[:len(a)]
    assert SEED == "schemarouter-multilingual-20261015-stress-v1"
    assert len({catalog_hash(x) for x in catalogs}) == len(catalogs)
    assert len(set(x["id"] for x in catalogs[-1])) == 500
    assert all(
        r["id"].startswith("dev_stress.")
        for r in catalogs[-1][13:]
    )


def test_stable_generated_catalog_is_independent_of_case_order() -> None:
    corpus, _ = load_development_corpus(CORPUS)
    shuffled = copy.deepcopy(corpus)
    shuffled["cases"].reverse()
    assert catalog_hash(expand_catalog(shuffled["catalog"], 500)) == (
        catalog_hash(expand_catalog(corpus["catalog"], 500))
    )


@pytest.mark.parametrize("bad_size", [0, 12, 14, 499, True, 501])
def test_unrecognized_scale_fails_closed(bad_size: object) -> None:
    corpus, _ = load_development_corpus(CORPUS)
    with pytest.raises(ValueError, match="size"):
        expand_catalog(corpus["catalog"], bad_size)  # type: ignore[arg-type]


def test_changed_supported_route_target_cannot_pass_preflight() -> None:
    corpus, _ = load_development_corpus(CORPUS)
    corpus["cases"][0]["expected_route"] = "nonexistent.route"
    with pytest.raises(ValueError, match="target"):
        check_corpus(corpus)


def test_malformed_unsupported_ground_truth_fails_closed() -> None:
    corpus, _ = load_development_corpus(CORPUS)
    unsupported = next(c for c in corpus["cases"] if c["kind"] == "unsupported")
    unsupported["expected_route"] = "materials.search"
    with pytest.raises(ValueError, match="unsupported"):
        check_corpus(corpus)

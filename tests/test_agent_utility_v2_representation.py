from __future__ import annotations

from collections import Counter
from pathlib import Path

import scripts.evaluate_agent_utility_v2_representation as evaluator
from benchmarks.agent_utility_v2_catalog import build_registry, development_rows
from scripts.generate_agent_utility_v2_dev import freeze_dev


def test_typed_multifield_ranks_semantic_and_unit_routes() -> None:
    documents = evaluator._documents(build_registry(100))
    retriever = evaluator.RepresentationRetriever(
        documents,
        "TYPED-MULTIFIELD",
    )

    resistance, _ = retriever.rank("electrical resistance value")
    assert resistance[0][0] == "electrical.resistance"

    diameter, _ = retriever.rank("particle diameter nm")
    assert diameter[0][0] == "geometry.particle_diameter_nm"

    read_record, _ = retriever.rank("read record without modifying it")
    assert read_record[0][0] == "records.read"


def test_representation_evaluator_consumes_frozen_dev_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    freeze_dir = tmp_path / "freeze"
    freeze_dev(freeze_dir)

    monkeypatch.setattr(evaluator, "CATALOG_SIZES", (100,))
    result = evaluator.evaluate(freeze_dir)

    assert result["surface"] == "development"
    assert result["freeze_manifest"]["confirmation_surface_opened"] is False
    assert result["conditions_scored"] == [
        "DESCRIPTION-ONLY",
        "RAW-SPEC",
        "TYPED-MULTIFIELD",
    ]
    assert "INTENT-MANUAL" in result["conditions_blocked"]
    assert "TYPED+INTENT" in result["conditions_blocked"]

    catalog = result["catalog_sizes"]["100"]
    assert set(catalog) == {
        "DESCRIPTION-ONLY",
        "RAW-SPEC",
        "TYPED-MULTIFIELD",
    }

    for condition in catalog.values():
        assert condition["aggregate"]["rows"] == 360
        assert condition["aggregate"]["supported_rows"] == 300
        assert condition["aggregate"]["unsupported_rows"] == 60
        assert condition["index_bytes"] > 0
        assert condition["index_build_seconds"] >= 0
        for k in ("1", "3", "5", "10"):
            assert 0.0 <= condition["aggregate"]["k"][k]["Recall"] <= 1.0
            assert 0.0 <= condition["aggregate"]["k"][k]["FullCoverage"] <= 1.0
            assert 0.0 <= condition["aggregate"]["k"][k]["nDCG"] <= 1.0

    gate = result["dev_gate_descriptive"]
    assert gate["comparator"] == "RAW-SPEC under BM25"
    assert gate["confirmation_claim_allowed"] is False


def _legacy_r8_typed_ranking(
    retriever: evaluator.RepresentationRetriever,
    query: str,
) -> list[tuple[str, float]]:
    query_counts = Counter(evaluator._tokens(query))
    route_count = len(retriever.route_ids)
    field_scores: list[list[float] | None] = [
        None
        for _ in retriever._typed_index_items
    ]
    field_touched: list[list[int] | None] = [
        None
        for _ in retriever._typed_index_items
    ]

    for position, (_, index) in enumerate(retriever._typed_index_items):
        for term, query_tf in query_counts.items():
            weights = index.weight_postings.get(term)
            if not weights:
                continue
            scores = field_scores[position]
            touched = field_touched[position]
            if scores is None:
                scores = [0.0] * route_count
                touched = []
                field_scores[position] = scores
                field_touched[position] = touched
            for route_id, contribution in weights.items():
                route_index = retriever._route_index[route_id]
                if scores[route_index] == 0.0:
                    touched.append(route_index)
                scores[route_index] += query_tf * contribution

    rrf = [0.0] * route_count
    rrf_touched: list[int] = []
    for scores, touched in zip(field_scores, field_touched, strict=True):
        if scores is None or not touched:
            continue
        ranked_indexes = sorted(
            touched,
            key=lambda route_index: (
                -scores[route_index],
                route_index,
            ),
        )
        for rank, route_index in enumerate(ranked_indexes, start=1):
            if rrf[route_index] == 0.0:
                rrf_touched.append(route_index)
            rrf[route_index] += retriever._rrf_weights[rank]

    positive_indexes = sorted(
        rrf_touched,
        key=lambda route_index: (
            -rrf[route_index],
            route_index,
        ),
    )
    route_ids = retriever.route_ids
    return [
        *[
            (route_ids[route_index], rrf[route_index])
            for route_index in positive_indexes
        ],
        *[
            (route_id, 0.0)
            for route_index, route_id in enumerate(route_ids)
            if rrf[route_index] == 0.0
        ],
    ]


def test_typed_runtime_fast_path_is_exactly_r8_equivalent() -> None:
    documents = evaluator._documents(build_registry(100))
    retriever = evaluator.RepresentationRetriever(
        documents,
        "TYPED-MULTIFIELD",
    )

    queries = [row["query"] for row in development_rows()]
    queries.extend(
        [
            "read only record value without changing state",
            "particle diameter value nm length",
            "permanently delete file destructive state-changing action",
            "formation energy per atom eV/atom",
        ]
    )

    for query in queries:
        actual, _ = retriever.rank(query)
        expected = _legacy_r8_typed_ranking(retriever, query)
        assert actual == expected

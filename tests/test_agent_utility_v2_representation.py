from __future__ import annotations

from pathlib import Path

import scripts.evaluate_agent_utility_v2_representation as evaluator
from benchmarks.agent_utility_v2_catalog import build_registry
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

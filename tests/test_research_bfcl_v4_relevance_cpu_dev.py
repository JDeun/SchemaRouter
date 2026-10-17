"""Synthetic control tests only; BFCL publisher originals run on Actions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter.decisions import EmbeddingDecisionBackend
from schemarouter.embedding_e5 import E5CachedEmbedder
from scripts.research_bfcl_v4_relevance_cpu_dev import (
    ORIGINAL_BLOBS,
    calibrate_threshold,
    default_lexical_one,
    embedding_one,
    evaluate,
    git_blob_sha1,
    load_jsonl,
    load_originals,
)

GOOD = {
    "name": "record_search.find",
    "description": "Search for academic records by keywords",
    "parameters": {
        "type": "dict", "properties": {
            "topic": {"type": "string", "description": "Keyword to search records"}
        },
    },
}
BAD = {
    "name": "image_generator.draw",
    "description": "Draw a painting from a description",
    "parameters": {"type": "dict", "properties": {
        "prompt": {"type": "string", "description": "Desired illustration"}
    }},
}


def fixture(tmp_path: Path) -> Path:
    records = {"multiple": [], "irrelevance": [], "gold": []}
    for number in range(200):
        records["multiple"].append({
            "id": f"multiple_{number}",
            "question": [[{"role": "user", "content": "Search academic papers about algae"}]],
            "function": [BAD, GOOD],
        })
        records["gold"].append({
            "id": f"multiple_{number}",
            "ground_truth": [{GOOD["name"]: {"topic": ["algae"]}}],
        })
    for number in range(240):
        records["irrelevance"].append({
            "id": f"irrelevance_{number}",
            "question": [[{"role": "user", "content": "Translate my recording"}]],
            "function": [BAD],
        })
    for kind, (filename, _, _) in ORIGINAL_BLOBS.items():
        raw = b"".join(
            json.dumps(row).encode("utf-8") + b"\n"
            for row in records[kind]
        )
        (tmp_path / filename).write_bytes(raw)
    return tmp_path


def test_original_publisher_blob_guard_and_exact_denominators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    location = fixture(tmp_path)
    source_hashes = {
        kind: (filename, git_blob_sha1((location / filename).read_bytes()), count)
        for kind, (filename, _, count) in ORIGINAL_BLOBS.items()
    }
    monkeypatch.setattr(
        "scripts.research_bfcl_v4_relevance_cpu_dev.ORIGINAL_BLOBS",
        source_hashes,
    )
    cases = load_originals(location)
    assert len(cases) == 440
    assert sum(z["split"] == "calibration" for z in cases) == 220
    assert sum(z["split"] == "evaluation" for z in cases) == 220
    assert sum(z["kind"] == "multiple" for z in cases) == 200
    assert all(z["expected"] == GOOD["name"] for z in cases if z["kind"] == "multiple")
    with pytest.raises(ValueError, match="source blob drift"):
        load_jsonl(
            location / "BFCL_v4_multiple.json",
            original_blob="0" * 40, count=200,
        )


def test_real_lexical_api_and_authorized_option_only():
    row = {
        "query": "Find records by keyword",
        "functions": [BAD, GOOD],
    }
    lexical, score = default_lexical_one(row)
    assert lexical in {BAD["name"], GOOD["name"]}
    assert isinstance(score, float)
    def fake_embeddings(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if text.startswith("query:") else [0.8, 0.6] for text in texts]
    semantic = EmbeddingDecisionBackend(
        E5CachedEmbedder(fake_embeddings),
    )
    route, similarity = embedding_one(row, semantic)
    assert route in {BAD["name"], GOOD["name"]}
    assert -1 <= similarity <= 1


def test_public_calibration_never_mislabels_separate_denominators():
    rows = [
        {
            "split": "calibration" if i % 2 == 0 else "evaluation",
            "kind": "multiple" if i < 200 else "irrelevance",
            "lexical_score": float(i) / 440,
        }
        for i in range(440)
    ]
    t = calibrate_threshold(rows, "lexical_score")
    calibration_negatives = [
        r for r in rows if r["split"] == "calibration" and r["kind"] == "irrelevance"
    ]
    assert sum(r["lexical_score"] >= t for r in calibration_negatives) <= 12
    assert len(calibration_negatives) == 120


def test_synthetic_encoder_is_never_claimed_real_model(tmp_path: Path, monkeypatch):
    fixture(tmp_path)
    source_hashes = {
        kind: (filename, git_blob_sha1((tmp_path / filename).read_bytes()), count)
        for kind, (filename, _, count) in ORIGINAL_BLOBS.items()
    }
    monkeypatch.setattr(
        "scripts.research_bfcl_v4_relevance_cpu_dev.ORIGINAL_BLOBS",
        source_hashes,
    )
    rows = load_originals(tmp_path)
    def fake(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if text.startswith("query:") else [0.8, 0.6] for text in texts]
    report = evaluate(rows, fake)
    assert report["case_count"] == 440
    assert report["real_model_inference_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["native_provider_tools_executed"] is False
    assert report["by_arm"]["lexical"]["evaluation"]["supported"] == 100
    assert report["by_arm"]["e5"]["evaluation"]["unsupported"] == 120
    assert "algae" not in json.dumps(report)

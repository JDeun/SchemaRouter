from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_agent_utility_corpus_identity.py"


def _module():
    spec = importlib.util.spec_from_file_location("corpus_identity_validator", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(module, surface: str) -> list[dict]:
    config = module.SURFACES[surface]
    stratum_key = config["stratum_key"]
    rows = []
    for slot in module.expected_slots(surface):
        rows.append(
            {
                "semantic_task_id": slot["semantic_task_id"],
                stratum_key: slot[stratum_key],
                "language": slot["language"],
                "query": f"independent query {slot['semantic_task_id']}",
            }
        )
    return rows


@pytest.mark.parametrize(
    ("surface", "expected"),
    [("heldout", 780), ("final-answer", 144)],
)
def test_corpus_identity_validator_accepts_exact_authoring_surface(
    surface: str,
    expected: int,
) -> None:
    module = _module()
    rows = _rows(module, surface)

    result = module.validate_rows(surface, rows)

    assert result["row_count"] == expected
    assert result["authoring_slot_count"] == expected
    assert result["normalized_query_count"] == expected
    assert len(result["identity_sha256"]) == 64
    assert len(result["query_content_sha256"]) == 64
    assert result["content_generation_authorized_by_validator"] is False
    assert result["inference_authorized_by_validator"] is False


@pytest.mark.parametrize("surface", ["heldout", "final-answer"])
def test_corpus_identity_validator_rejects_missing_slot(surface: str) -> None:
    module = _module()
    rows = _rows(module, surface)[:-1]

    with pytest.raises(ValueError, match="row count mismatch"):
        module.validate_rows(surface, rows)


@pytest.mark.parametrize("surface", ["heldout", "final-answer"])
def test_corpus_identity_validator_rejects_identity_drift(surface: str) -> None:
    module = _module()
    rows = _rows(module, surface)
    key = module.SURFACES[surface]["stratum_key"]
    rows[0][key] = "drifted"

    with pytest.raises(ValueError, match=f"{key} drifted"):
        module.validate_rows(surface, rows)


@pytest.mark.parametrize("surface", ["heldout", "final-answer"])
def test_corpus_identity_validator_rejects_language_drift(surface: str) -> None:
    module = _module()
    rows = _rows(module, surface)
    rows[0]["language"] = "drifted"

    with pytest.raises(ValueError, match="language drifted"):
        module.validate_rows(surface, rows)


@pytest.mark.parametrize("surface", ["heldout", "final-answer"])
def test_corpus_identity_validator_rejects_normalized_duplicate_query(
    surface: str,
) -> None:
    module = _module()
    rows = _rows(module, surface)
    rows[0]["query"] = "  SAME   QUERY "
    rows[1]["query"] = "same query"

    with pytest.raises(ValueError, match="normalized query text must be unique"):
        module.validate_rows(surface, rows)


@pytest.mark.parametrize("surface", ["heldout", "final-answer"])
def test_corpus_identity_validator_rejects_empty_query(surface: str) -> None:
    module = _module()
    rows = _rows(module, surface)
    rows[0]["query"] = "   "

    with pytest.raises(ValueError, match="query must be a non-empty string"):
        module.validate_rows(surface, rows)

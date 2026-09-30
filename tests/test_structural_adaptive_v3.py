from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)
from scripts.rank_agent_utility_v5_structural_adaptive_dev import (  # noqa: E402
    _verify_preregistered_identity,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-adaptive-depth-preregistration.json"
)


def test_structural_adaptive_v3_freezes_confirmed_core_weights() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    retriever = prereg["fixed_retriever"]

    assert retriever["candidate_id"] == "STRUCT-4.5-1.5"
    assert retriever["weights_retunable"] is False
    assert retriever["tool_identifier_bonus"] == (
        _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    )
    assert retriever["operation_family_bonus"] == (
        _STRUCTURAL_OPERATION_FAMILY_BONUS
    )
    assert prereg["independence"][
        "structural_confirmation_rows_allowed_for_adaptive_tuning"
    ] is False
    assert prereg["after_dev"]["fresh_confirmation_required"] is True


def test_structural_adaptive_v3_accepts_only_original_dev_identity() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    dev = prereg["development_surface"]
    manifest = {
        "task_rows_sha256": dev["task_rows_sha256"],
        "catalog_family_sha256": dev["catalog_family_sha256"],
        "catalogs": {
            size: {"sha256": digest}
            for size, digest in dev["catalog_sha256"].items()
        },
    }

    _verify_preregistered_identity(manifest, prereg)


def test_structural_adaptive_v3_rejects_dev_hash_drift() -> None:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    dev = prereg["development_surface"]
    manifest = {
        "task_rows_sha256": "0" * 64,
        "catalog_family_sha256": dev["catalog_family_sha256"],
        "catalogs": {
            size: {"sha256": digest}
            for size, digest in dev["catalog_sha256"].items()
        },
    }

    try:
        _verify_preregistered_identity(manifest, prereg)
    except RuntimeError as exc:
        assert "task hash drifted" in str(exc)
    else:
        raise AssertionError("DEV hash drift was not rejected")

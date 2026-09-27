from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_m3_fine_fusion_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_m3_fine_fusion_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fine fusion analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_weight_grid_is_frozen() -> None:
    module = _module()
    assert module.SCHEMA_WEIGHTS == (
        0.30,
        0.35,
        0.40,
        0.45,
        0.50,
        0.55,
        0.60,
    )

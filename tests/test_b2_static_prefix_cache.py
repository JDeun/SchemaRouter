from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_agent_utility_phase_b_smollm3.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("b2_eval_prefix", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_static_prefix_cache_is_opt_in_by_default() -> None:
    module = _load_module()

    assert module.STATIC_PREFIX_CACHE == "0"
    assert module.STATIC_PREFIX_CACHE_ENABLED is False

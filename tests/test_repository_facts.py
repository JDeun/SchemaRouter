from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_repository_facts.py"


def _module():
    spec = importlib.util.spec_from_file_location("sync_repository_facts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_facts_match_canonical_sources() -> None:
    module = _module()
    facts = module.load_facts()

    assert facts.stable_version == "0.13.0"
    assert facts.release_date == "2026-10-01"
    assert facts.experiment_count == 92
    assert facts.development_version == "0.14.0.dev0"
    module.check(facts)

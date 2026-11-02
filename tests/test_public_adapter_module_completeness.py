"""Prevent a newly added adapter module from escaping the public E2E matrix.

The canonical, OpenAPI/SQLAlchemy and generic-store manifests must together
cover every actual registered invoker module in schemarouter.adapters.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks"
ADAPTERS = ROOT / "src/schemarouter/adapters"
NON_EXECUTING_ADAPTER_MODULES = {
    "__init__.py",
    "base.py",
    "discovery_limits.py",
    "plugins.py",
}
SUPPLEMENTAL_NATIVE_MODULES = {
    "router.openapi.get": "openapi.py",
    "router.sqlalchemy.select": "sqlalchemy_database.py",
}


def test_every_adapter_invoker_family_is_registered_with_real_evidence() -> None:
    canonical = json.loads(
        (BASE / "public-execution-wiring-v1.json").read_text(encoding="utf-8")
    )
    other = json.loads(
        (BASE / "public-execution-adapter-gaps-v1.json").read_text(encoding="utf-8")
    )
    generic = json.loads(
        (BASE / "public-source-family-wiring-v1.json").read_text(encoding="utf-8")
    )
    actual = {
        path.name for path in ADAPTERS.glob("*.py")
    } - NON_EXECUTING_ADAPTER_MODULES

    represented = {
        Path(row["invoker"]).name
        for row in canonical["paths"]
        if row["invoker"].startswith("src/schemarouter/adapters/")
    }
    assert set(SUPPLEMENTAL_NATIVE_MODULES) == {
        row["id"] for row in other["paths"]
    }
    represented.update(SUPPLEMENTAL_NATIVE_MODULES.values())
    represented.update(Path(row["adapter"]).name for row in generic["paths"])

    assert represented == actual, {
        "uncovered_adapter_modules": sorted(actual - represented),
        "stale_manifest_adapters": sorted(represented - actual),
    }
    assert all(
        row["real_invoker_tests"] and row["denial_tests"]
        for row in canonical["paths"]
    )
    assert all(
        row["positive"] and row["negative"]
        for row in generic["paths"]
    )

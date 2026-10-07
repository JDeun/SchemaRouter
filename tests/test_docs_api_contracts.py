from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_docs_api_contracts.py"
MANIFEST = ROOT / ".github" / "docs-api-contracts.json"


def _module():
    spec = importlib.util.spec_from_file_location("check_docs_api_contracts", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_docs_api_contracts_match_installed_package() -> None:
    module = _module()

    assert module.validate_contracts(MANIFEST, root=ROOT) == []


def test_missing_public_symbol_is_reported(tmp_path: Path) -> None:
    module = _module()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["contracts"][0]["target"] = "schemarouter.DoesNotExist"
    path = tmp_path / "contracts.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = module.validate_contracts(path, root=ROOT)

    assert any("DoesNotExist" in error for error in errors)


def test_documented_default_drift_is_reported(tmp_path: Path) -> None:
    module = _module()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    vector = next(
        item
        for item in manifest["contracts"]
        if item["id"] == "vector.add_vector_store"
    )
    vector["parameters"]["default_top_k"]["default"] = 999
    path = tmp_path / "contracts.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = module.validate_contracts(path, root=ROOT)

    assert any("default_top_k" in error for error in errors)


def test_bilingual_document_reference_is_required(tmp_path: Path) -> None:
    module = _module()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["contracts"][0]["docs"].pop("ko")
    path = tmp_path / "contracts.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = module.validate_contracts(path, root=ROOT)

    assert any("missing docs.ko" in error for error in errors)

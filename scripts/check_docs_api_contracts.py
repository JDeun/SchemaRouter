#!/usr/bin/env python3
"""Validate contract-tagged documentation against the installed package."""

from __future__ import annotations

import importlib
import inspect
import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "api-contracts.json"
DOC_ROOTS = (ROOT / "docs", ROOT / "docs_ko")


def _load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise SystemExit("unsupported docs API contract manifest schema")
    return data


def _resolve(target: str) -> Any:
    parts = target.split(".")
    if len(parts) < 2:
        raise SystemExit(f"invalid contract target: {target}")
    module = importlib.import_module(parts[0])
    value: Any = module
    for part in parts[1:]:
        if not hasattr(value, part):
            raise SystemExit(f"documented public symbol does not exist: {target}")
        value = getattr(value, part)
    return value


def _parameter_default(parameter: inspect.Parameter) -> Any:
    if parameter.default is inspect.Parameter.empty:
        return None
    return parameter.default


def _check_callable(contract: dict[str, Any]) -> None:
    target = str(contract["target"])
    value = _resolve(target)
    if not callable(value):
        raise SystemExit(f"documented public symbol is not callable: {target}")
    signature = inspect.signature(value)
    parameters = signature.parameters
    for name, expected in contract.get("parameters", {}).items():
        if name not in parameters:
            raise SystemExit(f"{target}: documented parameter no longer exists: {name}")
        parameter = parameters[name]
        required = parameter.default is inspect.Parameter.empty
        if "required" in expected and required is not bool(expected["required"]):
            raise SystemExit(
                f"{target}.{name}: required={required!r}, expected {expected['required']!r}"
            )
        if "default" in expected and _parameter_default(parameter) != expected["default"]:
            raise SystemExit(
                f"{target}.{name}: default={_parameter_default(parameter)!r}, "
                f"expected {expected['default']!r}"
            )
        if expected.get("keyword_only") is True and (
            parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        ):
            raise SystemExit(f"{target}.{name}: documented keyword-only contract drifted")


def _check_model_default(contract: dict[str, Any]) -> None:
    target = str(contract["target"])
    model = _resolve(target)
    fields = getattr(model, "model_fields", None)
    if not isinstance(fields, dict):
        raise SystemExit(f"{target}: target is not a Pydantic model")
    field_name = str(contract["field"])
    if field_name not in fields:
        raise SystemExit(f"{target}: documented model field no longer exists: {field_name}")
    actual = fields[field_name].default
    expected = contract["default"]
    if actual != expected:
        raise SystemExit(
            f"{target}.{field_name}: default={actual!r}, expected {expected!r}"
        )


def _check_documents(contract: dict[str, Any]) -> None:
    contract_id = str(contract["id"])
    for relative in contract.get("documents", []):
        texts: list[str] = []
        for root in DOC_ROOTS:
            path = root / relative
            if not path.is_file():
                raise SystemExit(
                    f"{contract_id}: missing bilingual contract document: {path}"
                )
            texts.append(path.read_text(encoding="utf-8"))
        for snippet in contract.get("snippets", []):
            for root, text in zip(DOC_ROOTS, texts, strict=True):
                if snippet not in text:
                    raise SystemExit(
                        f"{contract_id}: contract snippet {snippet!r} missing from "
                        f"{root / relative}"
                    )


def _check_extras(data: dict[str, Any]) -> None:
    package = str(data["package"])
    declared = set(metadata.metadata(package).get_all("Provides-Extra") or [])
    expected = set(data.get("extras", []))
    if declared != expected:
        raise SystemExit(
            f"documented optional extras drifted: installed={sorted(declared)!r}, "
            f"expected={sorted(expected)!r}"
        )


def _check_cli(data: dict[str, Any]) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "schemarouter.cli", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    for token in data.get("cli_help_tokens", []):
        if token not in output:
            raise SystemExit(f"documented CLI token missing from --help: {token!r}")


def main() -> None:
    data = _load_manifest()
    ids: set[str] = set()
    for contract in data.get("contracts", []):
        contract_id = str(contract["id"])
        if contract_id in ids:
            raise SystemExit(f"duplicate docs contract id: {contract_id}")
        ids.add(contract_id)
        _check_callable(contract)
        _check_documents(contract)
    for contract in data.get("model_defaults", []):
        contract_id = str(contract["id"])
        if contract_id in ids:
            raise SystemExit(f"duplicate docs contract id: {contract_id}")
        ids.add(contract_id)
        _check_model_default(contract)
        _check_documents(contract)
    _check_extras(data)
    _check_cli(data)
    print(
        f"documented public API contracts OK: "
        f"{len(data.get('contracts', []))} callables, "
        f"{len(data.get('model_defaults', []))} defaults"
    )


if __name__ == "__main__":
    main()

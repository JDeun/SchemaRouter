from __future__ import annotations

import argparse
import importlib
import inspect
import json
from importlib import metadata
from pathlib import Path
from typing import Any


def _resolve_target(target: str) -> Any:
    parts = target.split(".")
    if not parts or not parts[0]:
        raise ValueError("target must be a dotted import path")
    value: Any = importlib.import_module(parts[0])
    for part in parts[1:]:
        value = getattr(value, part)
    return value


def _validate_docs_reference(
    *,
    contract_id: str,
    docs: object,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(docs, dict):
        errors.append(f"{contract_id}: docs must be an object")
        return

    needle = docs.get("needle")
    if not isinstance(needle, str) or not needle:
        errors.append(f"{contract_id}: docs.needle must be a non-empty string")
        return

    for language in ("en", "ko"):
        relative = docs.get(language)
        if not isinstance(relative, str) or not relative:
            errors.append(f"{contract_id}: missing docs.{language} path")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"{contract_id}: missing {language} documentation: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if needle not in text:
            errors.append(
                f"{contract_id}: {relative} does not contain documented token {needle!r}"
            )


def _validate_parameters(
    *,
    contract_id: str,
    target: Any,
    parameters: object,
    errors: list[str],
) -> None:
    if not isinstance(parameters, dict):
        errors.append(f"{contract_id}: parameters must be an object")
        return

    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError) as exc:
        errors.append(f"{contract_id}: target has no inspectable signature: {exc}")
        return

    for name, expected in parameters.items():
        if name not in signature.parameters:
            errors.append(f"{contract_id}: missing documented keyword {name!r}")
            continue
        if not isinstance(expected, dict):
            errors.append(f"{contract_id}.{name}: contract must be an object")
            continue

        parameter = signature.parameters[name]
        if expected.get("required") is True:
            if parameter.default is not inspect.Parameter.empty:
                errors.append(
                    f"{contract_id}.{name}: documented required parameter has "
                    f"default {parameter.default!r}"
                )

        if "default" in expected:
            actual = parameter.default
            wanted = expected["default"]
            if actual is inspect.Parameter.empty:
                errors.append(
                    f"{contract_id}.{name}: expected default {wanted!r}, "
                    "but parameter is required"
                )
            elif actual != wanted:
                errors.append(
                    f"{contract_id}.{name}: documented default {wanted!r} "
                    f"!= installed default {actual!r}"
                )


def _installed_extras(distribution: str) -> set[str]:
    package_metadata = metadata.metadata(distribution)
    return set(package_metadata.get_all("Provides-Extra") or ())


def validate_contracts(
    manifest_path: Path,
    *,
    root: Path,
    distribution: str = "schemarouter",
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load API contract manifest: {exc}"]

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return ["unsupported API contract manifest schema"]

    contracts = manifest.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        errors.append("manifest contracts must be a non-empty list")
        contracts = []

    seen_ids: set[str] = set()
    for raw in contracts:
        if not isinstance(raw, dict):
            errors.append("contract entry must be an object")
            continue

        contract_id = raw.get("id")
        target_name = raw.get("target")
        kind = raw.get("kind")
        if not isinstance(contract_id, str) or not contract_id:
            errors.append("contract id must be a non-empty string")
            continue
        if contract_id in seen_ids:
            errors.append(f"duplicate contract id: {contract_id}")
            continue
        seen_ids.add(contract_id)

        if not isinstance(target_name, str) or not target_name:
            errors.append(f"{contract_id}: target must be a dotted import path")
            continue
        try:
            target = _resolve_target(target_name)
        except (ImportError, AttributeError, ValueError) as exc:
            errors.append(f"{contract_id}: cannot resolve {target_name!r}: {exc}")
            continue

        _validate_docs_reference(
            contract_id=contract_id,
            docs=raw.get("docs"),
            root=root,
            errors=errors,
        )

        if kind == "callable":
            if not callable(target):
                errors.append(f"{contract_id}: target is not callable")
            _validate_parameters(
                contract_id=contract_id,
                target=target,
                parameters=raw.get("parameters", {}),
                errors=errors,
            )
        elif kind == "symbol":
            pass
        else:
            errors.append(f"{contract_id}: unsupported contract kind {kind!r}")

    expected_extras = manifest.get("extras")
    if not isinstance(expected_extras, list) or not all(
        isinstance(item, str) and item for item in expected_extras
    ):
        errors.append("manifest extras must be a list of non-empty strings")
    else:
        installed = _installed_extras(distribution)
        expected = set(expected_extras)
        if installed != expected:
            missing = sorted(expected - installed)
            undocumented = sorted(installed - expected)
            if missing:
                errors.append(f"documented extras missing from package metadata: {missing}")
            if undocumented:
                errors.append(
                    f"installed extras missing from docs contract manifest: {undocumented}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(".github/docs-api-contracts.json"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--distribution", default="schemarouter")
    args = parser.parse_args()

    errors = validate_contracts(
        args.manifest,
        root=args.root,
        distribution=args.distribution,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("documented public API contracts match the installed package")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

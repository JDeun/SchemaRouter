"""Preflight independently authored SafeAct V1 contract source file hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    from scripts.validate_safeact_v1_contract_provenance import validate
except ModuleNotFoundError:
    from validate_safeact_v1_contract_provenance import validate


def verify_sources(document: dict[str, object], source_root: Path) -> list[str]:
    """Verify source identity, not independent authorship or policy semantics."""
    errors = validate(document)
    if errors:
        return errors
    root = source_root.resolve()
    if not root.is_dir():
        return [f"trusted public source root is not a directory: {source_root}"]
    contracts = document["contracts"]
    assert isinstance(contracts, list)
    for contract_index, contract in enumerate(contracts):
        assert isinstance(contract, dict)
        sources = contract["sources"]
        assert isinstance(sources, list)
        for source_index, source in enumerate(sources):
            assert isinstance(source, dict)
            label = f"contracts[{contract_index}].sources[{source_index}]"
            expected = source.get("sha256")
            if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
                errors.append(f"{label}: missing or invalid frozen sha256")
                continue
            relative = source["path"]
            assert isinstance(relative, str)
            current = root
            unsafe = False
            for component in relative.replace("\\", "/").split("/"):
                current = current / component
                if current.is_symlink():
                    errors.append(f"{label}: trusted public source path contains a symlink")
                    unsafe = True
                    break
            if unsafe:
                continue
            if not current.is_file() or not current.resolve().is_relative_to(root):
                errors.append(f"{label}: source missing or outside trusted public root")
                continue
            digest = hashlib.sha256()
            with current.open("rb") as reader:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                errors.append(f"{label}: frozen public source sha256 mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract_file", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.contract_file.read_text(encoding="utf-8"))
    errors = verify_sources(document, args.source_root)
    for error in errors:
        print("ERROR:", error)
    if errors:
        return 1
    print("SafeAct V1 public-source identity OK (authorship is not verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

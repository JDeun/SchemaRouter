"""Inventory pinned public V1 tool interfaces without loading gold or task data.

This is an *unreviewed* aid to independent contract authorship, NOT an
Evidence Contract and NOT a scored SafeActBench run.  Only file identity and
SHA-256 of public tool implementations are recorded. Never open env/data,
world state, case manifests, labels, scenarios or evaluator sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

PINNED_REVISION = "841816cf1e376e6fbf8600cffac5df1736e1d369"
PUBLIC_DOMAINS = (
    "customer_policy_qa",
    "legal_finance_advice",
    "ops_code_agent",
    "research_assistant",
)


def build_inventory(root: Path) -> dict[str, Any]:
    """Inspect only templates/<fixed-domain>/tools/*.py, without code parsing."""
    root = root.resolve(strict=True)
    records: list[dict[str, str]] = []
    for domain in PUBLIC_DOMAINS:
        folder = root / "templates" / domain / "tools"
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError(f"missing or symlinked public tool folder: {domain}")
        for path in sorted(folder.iterdir()):
            if path.name.startswith("_") or path.name == "mock_tool.py":
                continue
            if path.suffix != ".py":
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"unsafe public tool path: {domain}/{path.name}")
            if not path.resolve().is_relative_to(root):
                raise ValueError(
                    f"public tool escapes pinned root: {domain}/{path.name}"
                )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            records.append({
                "domain": domain,
                "tool_name": path.stem,
                "source_path": path.relative_to(root).as_posix(),
                "source_sha256": digest,
            })
    if not records:
        raise ValueError("public V1 tool interface inventory is empty")
    return {
        "schema_version": 1,
        "kind": "safeact_v1_public_tool_filename_inventory_only",
        "upstream_revision": PINNED_REVISION,
        "independently_authored_contracts": False,
        "human_reviewed": False,
        "scored_experiment": False,
        "case_coverage": None,
        "forbidden_sources_read": False,
        "tools": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("safeact_root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.safeact_root.resolve(strict=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if revision != PINNED_REVISION:
        raise ValueError("SafeAct upstream revision is not pinned")
    data = build_inventory(root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Unreviewed public tool interface inventory: {len(data['tools'])} entries; "
        "NO contracts approved or model scores produced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

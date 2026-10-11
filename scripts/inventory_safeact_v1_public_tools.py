"""Inventory pinned public V1 tool interfaces without loading gold or task data.

This is an *unreviewed* aid to independent contract authorship, NOT an
Evidence Contract and NOT a scored SafeActBench run.  Only file identity and
SHA-256 of public tool implementations and fixed template/world/policies
candidate files are recorded. Never open env/data, other world state,
case manifests, labels, scenarios or evaluator sources.
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
PUBLIC_POLICY_SUFFIXES = frozenset({".json", ".md", ".txt", ".yaml", ".yml"})


def build_inventory(root: Path) -> dict[str, Any]:
    """Hash fixed public template tools and policy candidates, without parsing."""
    root = root.resolve(strict=True)
    records: list[dict[str, str]] = []
    policy_candidates: list[dict[str, str]] = []
    domains_without_policy_directory: list[str] = []
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
        # Only the fixed, public template policy directory is admissible.
        # Never enumerate env/, case manifests, other world-state folders,
        # hidden scenario requirements or evaluator artifacts.
        policy_dir = root / "templates" / domain / "world" / "policies"
        if policy_dir.is_symlink():
            raise ValueError(f"symlinked public policy directory: {domain}")
        if not policy_dir.exists():
            domains_without_policy_directory.append(domain)
            continue
        if not policy_dir.is_dir():
            raise ValueError(f"invalid public policy directory: {domain}")
        for path in sorted(policy_dir.iterdir()):
            if (
                path.is_symlink()
                or not path.is_file()
                or path.suffix.lower() not in PUBLIC_POLICY_SUFFIXES
                or not path.resolve().is_relative_to(root)
            ):
                raise ValueError(
                    f"unsafe public policy candidate: {domain}/{path.name}"
                )
            policy_candidates.append({
                "domain": domain,
                "source_path": path.relative_to(root).as_posix(),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
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
        "public_policy_candidates": policy_candidates,
        "domains_without_policy_directory": domains_without_policy_directory,
        "policy_candidates_are_contracts": False,
        "policy_candidates_are_runtime_observations": False,
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
        f"Unreviewed public tool interfaces: {len(data['tools'])}; "
        f"public-policy source candidates: {len(data['public_policy_candidates'])}; "
        "NO contract semantics, approvals or model scores produced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

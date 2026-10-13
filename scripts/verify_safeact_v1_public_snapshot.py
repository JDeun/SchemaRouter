"""Verify only frozen public SafeAct policy candidate bytes, never hidden gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

UPSTREAM = "841816cf1e376e6fbf8600cffac5df1736e1d369"
DOMAINS = {"customer_policy_qa", "legal_finance_advice", "research_assistant"}
PUBLIC = re.compile(
    r"templates/([a-z_]+)/world/policies/[a-z0-9_-]+\.(?:md|json|txt|yaml|yml)\Z"
)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()


def audit(doc: dict, source_root: Path, upstream_root: Path) -> list[str]:
    if (
        doc.get("kind") != "safeact_v1_unreviewed_public_policy_snapshot"
        or doc.get("upstream_revision") != UPSTREAM
        or doc.get("contracts_authored") is not False
        or doc.get("independently_approved") is not False
        or doc.get("scored_run_authorized") is not False
    ):
        return ["untrusted or approved-looking policy snapshot"]
    sources = doc.get("sources")
    if not isinstance(sources, list) or not sources:
        return ["missing candidate sources"]
    root, upstream = source_root.resolve(), upstream_root.resolve()
    seen: set[str] = set()
    errors: list[str] = []
    for index, entry in enumerate(sources):
        if not isinstance(entry, dict):
            errors.append(f"sources[{index}]: malformed entry")
            continue
        path, sha = entry.get("path"), entry.get("source_git_blob_sha1")
        match = PUBLIC.fullmatch(path) if isinstance(path, str) else None
        if not match or match.group(1) not in DOMAINS:
            errors.append(f"sources[{index}]: forbidden source path")
            continue
        if path in seen:
            errors.append(f"sources[{index}]: duplicate source path")
            continue
        seen.add(path)
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            errors.append(f"sources[{index}]: malformed pinned Git blob")
            continue
        files = [root / path, upstream / path]
        if any(item.is_symlink() for f in files for item in (f, *f.parents)):
            errors.append(f"sources[{index}]: symlinked path")
            continue
        if any(not f.is_file() or git_blob_sha(f.read_bytes()) != sha for f in files):
            errors.append(f"sources[{index}]: mismatch with pinned public source")
    unexpected = {
        f.relative_to(root).as_posix() for f in root.rglob("*")
        if f.is_file() or f.is_symlink()
    } - seen
    if unexpected:
        errors.append("undeclared source files")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--upstream-root", type=Path, required=True)
    args = parser.parse_args()
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=args.upstream_root,
        check=True, text=True, capture_output=True,
    ).stdout.strip()
    if sha != UPSTREAM:
        raise ValueError("unfrozen upstream revision")
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = audit(doc, args.source_root, args.upstream_root)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    for entry in doc["sources"]:
        f = args.source_root / entry["path"]
        print("UNREVIEWED sha256=" + hashlib.sha256(f.read_bytes()).hexdigest()
              + " " + entry["path"])
    print("Pinned public source bytes verified; no contract approved or model run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Revalidate the ClicShopping 4.33 inventory against a pinned local Git tree.

No PHP execution, live endpoints, credentials, model calls or scoring.  This is
a public-source integrity check, not evidence of deployment reachability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PINNED_UPSTREAM = "3bac851759234a4babb49d3f351e472cd9e0f31f"
APP_ROOT = Path("Core/ClicShopping/Apps/Tools/MCP")
ACTIONS = re.compile(r"private\s+const\s+([A-Z_]+)\s*=\s*\[(.*?)\];", re.S)
READ_TOKEN = re.compile(r"'([^']+)'\s*(?:,|$)", re.M)
WRITE_TOKEN = re.compile(r"'([^']+)'\s*=>", re.M)

SOURCES = {
    "AnthropicEcommerce": ("READ_ACTIONS", "WRITE_ACTIONS"),
    "CustomersProducts": ("READ_ACTIONS", "WRITE_ACTIONS"),
    "customerOrders": ("READ_ACTIONS", "WRITE_ACTIONS"),
    "ChatRagBI": ("ALLOWED_ACTIONS", None),
}
ROUTES = {
    "AnthropicEcommerce": "mcp&AnthropicEcommerce",
    "CustomersProducts": "mcp&customersProducts",
    "customerOrders": "mcp&customerOrders",
    "ChatRagBI": "mcp&ChatRagBI",
}


def git_blob_sha(raw: bytes) -> str:
    """Reproduce the SHA-1 blob identity used by the pinned Git repository."""
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def php_action_arrays(text: str) -> dict[str, tuple[str, ...]]:
    """Extract explicitly declared permissions, never infer route callability."""
    arrays: dict[str, tuple[str, ...]] = {}
    for match in ACTIONS.finditer(text):
        key, body = match.groups()
        if key in arrays:
            raise ValueError(f"duplicate action policy: {key}")
        names = WRITE_TOKEN.findall(body) if key == "WRITE_ACTIONS" else READ_TOKEN.findall(body)
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate action name in {key}")
        arrays[key] = tuple(names)
    return arrays


def audit(upstream_root: Path, inventory: dict) -> dict:
    if inventory.get("upstream", {}).get("commit") != PINNED_UPSTREAM:
        raise ValueError("ClicShopping pinned revision drift")
    # Git checkout verification prevents a newer branch revision from being
    # silently presented as source for the historical protocol.
    import subprocess
    head = subprocess.check_output(
        ["git", "-C", str(upstream_root), "rev-parse", "HEAD"], text=True,
    ).strip()
    if head != PINNED_UPSTREAM:
        raise ValueError(f"upstream checkout is not exact pinned revision: {head}")

    read_count = 0
    checked: list[str] = []
    endpoints = inventory["endpoints"]
    if set(endpoints) != set(SOURCES):
        raise ValueError("four historical endpoint matrices required")

    def source_bytes(entry: dict, *, missing_allowed: bool = False) -> bytes | None:
        nonlocal read_count
        path = str(entry["path"])
        candidate = Path(path)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not path.startswith(str(APP_ROOT) + "/")
        ):
            raise ValueError(f"unsafe upstream path: {path}")
        target = upstream_root / candidate
        if missing_allowed:
            if target.exists():
                raise ValueError(f"previously absent public page now present: {path}")
            return None
        raw = target.read_bytes()
        if git_blob_sha(raw) != entry.get("git_blob_sha"):
            raise ValueError(f"Git blob SHA mismatch for {path}")
        checked.append(path)
        read_count += 1
        return raw

    for name, (read_key, write_key) in SOURCES.items():
        endpoint = endpoints[name]
        page = endpoint["page_source"]
        absent = name == "customerOrders"
        source_bytes(page, missing_allowed=absent)
        policy_raw = source_bytes(endpoint["permission_source"])
        assert policy_raw is not None
        actions = php_action_arrays(policy_raw.decode("utf-8-sig"))
        read = list(actions.get(read_key, ()))
        write = list(actions.get(write_key, ())) if write_key else []
        if sorted(read) != sorted(endpoint["read_actions"]):
            raise ValueError(f"{name}: declared read action set changed")
        if sorted(write) != sorted(endpoint["write_actions"]):
            raise ValueError(f"{name}: declared write action set changed")
        if not read or set(read) & set(write):
            raise ValueError(f"{name}: malformed/overlapping action permissions")
        if absent and endpoint["status"] != "permissions_only_unverified_endpoint":
            raise ValueError("customerOrders must remain non-callable in frozen fixture")

    routes_entry = {
        "path": str(APP_ROOT / "clicshopping.json"),
        "git_blob_sha": "18ed3a59ca7b73a7c68653615baa86db076a45e6",
    }
    route_raw = source_bytes(routes_entry)
    assert route_raw is not None
    routes = json.loads(route_raw)["routes"]["Shop"]
    for endpoint, route in ROUTES.items():
        if route not in routes:
            raise ValueError(f"missing declared public route: {endpoint}")
    assert read_count == 8  # 4 permission sources + 3 pages + app router
    return {
        "status": "upstream_pinned_public_source_verified",
        "scored": False,
        "model_calls": 0,
        "live_endpoint_requests": 0,
        "upstream_commit": head,
        "files_checked": checked,
        "verified_source_count": read_count,
        "historical_noncallable_endpoint": "customerOrders",
        "note": (
            "This does not establish runtime URL reachability "
            "or independent benchmark validity."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument(
        "--inventory", type=Path,
        default=Path("benchmarks/external-validation-clicshopping-v433/source-inventory.json"),
    )
    args = parser.parse_args()
    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    print(json.dumps(audit(args.upstream_root, data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Verify ClicShopping's maintainer-directed 8ada7f1 source repin offline.

This deliberately preserves the historical 3bac851 development fixture.
It verifies source/route integrity only: no PHP, credentials, endpoints, or model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from scripts.validate_clicshopping_v433_inventory import validate_inventory

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks/external-validation-clicshopping-v433"
HISTORICAL = "3bac851759234a4babb49d3f351e472cd9e0f31f"
REPinned = "8ada7f1f392f3dd2800e825dac8d245dfd53944a"
APP = "Core/ClicShopping/Apps/Tools/MCP/"
NEW_PAGE = APP + "Sites/Shop/Pages/CustomerOrders/CustomerOrders.php"
NEW_README = APP + "Sites/Shop/Pages/CustomerOrders/readme.md"
ROUTE_PATH = APP + "clicshopping.json"
NEW_PAGE_SHA = "067d96233780bb52cbfd1eb9dee28e2c8697e099"
NEW_README_SHA = "545c092fe2d64e269390a37b9d9d9448bf5272e4"
NEW_ROUTE_SHA = "4762eaeecc5e672557da9280d6ebdcea8026c483"
OLD_ROUTE_SHA = "18ed3a59ca7b73a7c68653615baa86db076a45e6"
ORDER_READ = {"list_orders", "read_order", "history"}
ORDER_WRITE = {"cancel_order", "send_message"}
ACTION_DISPATCH = re.compile(
    r"'([a-z_]+)'\s*=>\s*\$this->(handle[A-Za-z]+)\s*\(", re.M
)


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def dispatch_actions(php: str) -> set[str]:
    """Read only literal PHP match dispatch arms; never invoke the PHP source."""
    pairs = ACTION_DISPATCH.findall(php)
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        raise ValueError("duplicate customerOrders action dispatch")
    return set(names)


def source_bytes(root: Path, rel: str, expected_sha: str) -> bytes:
    relative = Path(rel)
    if (relative.is_absolute() or ".." in relative.parts
            or not rel.startswith(APP)):
        raise ValueError("untrusted public-source path")
    file = (root / relative).resolve()
    if not file.is_relative_to(root.resolve()):
        raise ValueError("source path escapes pinned checkout")
    raw = file.read_bytes()
    if git_blob_sha(raw) != expected_sha:
        raise ValueError(f"pinned Git blob mismatch: {rel}")
    return raw


def verify(
    upstream_root: Path, plan: dict[str, Any], historic: dict[str, Any]
) -> dict[str, Any]:
    if validate_inventory(historic):
        raise ValueError("historical source matrix changed")
    if (plan.get("schema_version") != 1
            or plan.get("historical_dev_pin") != HISTORICAL
            or plan.get("new_source_pin") != REPinned
            or plan.get("upstream_repository") != "ClicShopping/ClicShopping"
            or plan.get("upstream_ref") != "version4.33"
            or historic["upstream"]["commit"] != HISTORICAL):
        raise ValueError("maintainer source transition is not exact")
    boundary = plan.get("source_verification", {})
    expected_boundary = {
        "offline_only": True,
        "credential_use": False,
        "live_endpoint_calls": 0,
        "php_execution": False,
        "model_calls": 0,
        "official_model_scored": False,
        "heldout_approved": False,
    }
    if boundary != expected_boundary:
        raise ValueError("source-only evaluation boundary changed")
    head = subprocess.check_output(
        ["git", "-C", str(upstream_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != REPinned:
        raise ValueError("source checkout is not the maintainer-pinned commit")
    expected_unchanged: dict[str, str] = {}
    for endpoint in historic["endpoints"].values():
        permission = endpoint["permission_source"]
        expected_unchanged[permission["path"]] = permission["git_blob_sha"]
        if endpoint["page_source"]["present"]:
            page = endpoint["page_source"]
            expected_unchanged[page["path"]] = page["git_blob_sha"]
    if plan.get("unchanged_git_blobs") != expected_unchanged:
        raise ValueError("historical permission/page source identity drift")
    for path, sha in expected_unchanged.items():
        source_bytes(upstream_root, path, sha)

    before = plan.get("route_before", {})
    after = plan.get("route_after", {})
    if (before.get("path") != ROUTE_PATH
            or before.get("git_blob_sha") != OLD_ROUTE_SHA
            or before.get("customer_orders") != r"Sites\Shop\Pages\customerOrders"
            or after.get("path") != ROUTE_PATH
            or after.get("git_blob_sha") != NEW_ROUTE_SHA
            or after.get("customer_orders") != r"Sites\Shop\Pages\CustomerOrders"):
        raise ValueError("upstream route correction is not pinned")
    route = json.loads(
        source_bytes(upstream_root, ROUTE_PATH, NEW_ROUTE_SHA)
    )["routes"]["Shop"].get("mcp&customerOrders")
    if route != after["customer_orders"]:
        raise ValueError("customerOrders route is not mapped to the new page")

    page = plan.get("new_customer_orders_page", {})
    readme = plan.get("new_customer_orders_readme", {})
    if (page.get("path") != NEW_PAGE or page.get("git_blob_sha") != NEW_PAGE_SHA
            or set(page.get("read_actions", ())) != ORDER_READ
            or set(page.get("write_actions", ())) != ORDER_WRITE
            or readme.get("path") != NEW_README
            or readme.get("git_blob_sha") != NEW_README_SHA):
        raise ValueError("customerOrders public-page evidence drift")
    php = source_bytes(upstream_root, NEW_PAGE, NEW_PAGE_SHA).decode("utf-8-sig")
    docs = source_bytes(upstream_root, NEW_README, NEW_README_SHA).decode("utf-8")
    if dispatch_actions(php) != ORDER_READ | ORDER_WRITE:
        raise ValueError("new customerOrders dispatch does not match permission actions")
    if ("canPerformAction" not in php
            or "CustomerOrdersPermissions" not in php
            or "customer_id" not in docs):
        raise ValueError("customerOrders public authentication/permission contract absent")
    original = historic["endpoints"]["customerOrders"]
    if (set(original["read_actions"]) != ORDER_READ
            or set(original["write_actions"]) != ORDER_WRITE
            or original["page_source"]["present"] is not False):
        raise ValueError("historical permission-only evidence must remain intact")
    return {
        "status": "new_customer_orders_public_source_verified",
        "source_pin": head,
        "prior_development_pin_preserved": HISTORICAL,
        "unchanged_source_blobs": len(expected_unchanged),
        "verified_new_customer_orders_dispatch_actions": sorted(
            ORDER_READ | ORDER_WRITE
        ),
        "verified_public_file_count": len(expected_unchanged) + 3,
        "native_surface": "REST endpoint/action matrix, not MCP tools/list",
        "customer_scope": (
            "README documents trusted-client customer_id; "
            "runtime tenant enforcement NOT verified by this static audit"
        ),
        "scored": False,
        "independent_heldout_authorized": False,
        "live_requests": 0,
        "model_calls": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--upstream-root", type=Path, required=True)
    p.add_argument("--plan", type=Path, default=PACKAGE / "maintainer-repin-8ada7f1.json")
    p.add_argument("--historical", type=Path, default=PACKAGE / "source-inventory.json")
    args = p.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    historic = json.loads(args.historical.read_text(encoding="utf-8"))
    print(json.dumps(verify(args.upstream_root, plan, historic), indent=2))


if __name__ == "__main__":
    main()

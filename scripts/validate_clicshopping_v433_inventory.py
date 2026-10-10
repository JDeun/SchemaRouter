"""Validate the pinned, offline-only ClicShopping 4.33 source inventory.

This is source-contract validation, not a scored router benchmark.
No network, credentials, PHP execution or model calls are performed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_INVENTORY = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/external-validation-clicshopping-v433/source-inventory.json"
)
COMMIT = "3bac851759234a4babb49d3f351e472cd9e0f31f"
SHA = re.compile(r"^[a-f0-9]{40}$")
OVERLAP = {
    "products", "product", "search", "categories", "stats", "recommendations"
}
EXPECTED = {
    "AnthropicEcommerce": (15, 7),
    "CustomersProducts": (6, 0),
    "customerOrders": (3, 2),
    "ChatRagBI": (10, 0),
}


def validate_inventory(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(data.get("schema_version") == 1, "schema_version must be 1")
    require(data.get("kind") == "clicshopping-4.33-public-endpoint-action-inventory",
            "unrecognized inventory kind")
    upstream = data.get("upstream", {})
    require(upstream.get("repository") == "ClicShopping/ClicShopping",
            "upstream repository mismatch")
    require(upstream.get("ref") == "version4.33", "upstream branch mismatch")
    require(upstream.get("commit") == COMMIT, "upstream revision is not pinned")
    comparison = data.get("comparison", {})
    require(comparison.get("native_interface") ==
            "REST endpoint/action matrix (not MCP tools/list or JSON-RPC inputSchema)",
            "must not pretend this is an MCP JSON-RPC schema")
    require(comparison.get("status") == "source_audit_not_scored",
            "inventory must not masquerade as a scored evaluation")
    require(comparison.get("model_calls") == 0, "model scoring is not evidenced")
    require(comparison.get("live_requests") == 0, "live endpoint use is not allowed")
    require(comparison.get("credential_use") is False, "no credentials allowed")
    require(comparison.get("field_recall_comparable") is False,
            "published REST action matrices have no common field-label contract")

    endpoints = data.get("endpoints", {})
    require(set(endpoints) == set(EXPECTED), "the four expected endpoints must be present")
    for name, counts in EXPECTED.items():
        ep = endpoints.get(name, {})
        page = ep.get("page_source", {})
        permission = ep.get("permission_source", {})
        read = ep.get("read_actions", [])
        write = ep.get("write_actions", [])
        require((len(read), len(write)) == counts, f"{name}: action counts drift")
        require(all(isinstance(a, str) and a for a in read + write),
                f"{name}: invalid action name")
        require(len(set(read + write)) == len(read + write),
                f"{name}: duplicate or read/write-overlapping actions")
        require(permission.get("path", "").startswith(
            "Core/ClicShopping/Apps/Tools/MCP/"
        ), f"{name}: missing source path")
        require(bool(SHA.fullmatch(permission.get("git_blob_sha", ""))),
                f"{name}: invalid pinned permission blob")
        require(page.get("path", "").startswith(
            "Core/ClicShopping/Apps/Tools/MCP/Sites/Shop/Pages/"
        ), f"{name}: invalid page path")
        if name == "customerOrders":
            require(page.get("present") is False
                    and page.get("status") == "not_in_pinned_tree"
                    and ep.get("status") == "permissions_only_unverified_endpoint",
                    "customerOrders page was absent at the pinned revision")
            require("customers_id" in ep.get("authentication_scope", ""),
                    "customerOrders requires authenticated customers_id")
        else:
            require(page.get("present") is True
                    and ep.get("status") == "page_and_permissions_verified",
                    f"{name}: missing dispatch source")
            require(bool(SHA.fullmatch(page.get("git_blob_sha", ""))),
                    f"{name}: invalid pinned page blob")

    anth = endpoints.get("AnthropicEcommerce", {})
    require(set(anth.get("dispatch_actions", [])) ==
            set(anth.get("read_actions", [])) | set(anth.get("write_actions", [])),
            "AnthropicEcommerce dispatch/permission mismatch")
    customers = endpoints.get("CustomersProducts", {})
    require(set(customers.get("dispatch_actions", [])) ==
            set(customers.get("read_actions", [])),
            "CustomersProducts dispatch/permission mismatch")
    require(customers.get("write_actions") == [], "CustomersProducts must remain read-only")
    require("DISPLAY_BROWSER_JSON" in customers.get("configuration_boundary", ""),
            "CustomersProducts configuration gating omitted")
    rag = endpoints.get("ChatRagBI", {})
    require(rag.get("write_actions") == [], "RAG-BI must remain read-only")
    require("RATE_LIMITED" in rag.get("response_contract", "")
            and "ai_disclaimer" in rag.get("response_contract", ""),
            "4.33 typed RAG-BI response contract omitted")
    require("no write/admin flags" in rag.get("authorization_model", ""),
            "RAG-BI principal restrictions omitted")

    overlap = data.get("overlap_actions", {})
    observed = (
        set(anth.get("read_actions", []))
        & set(customers.get("read_actions", []))
    )
    require(observed == OVERLAP, "overlap surface drift")
    require(set(overlap.get("shared", [])) == observed
            and overlap.get("count") == len(observed),
            "reported Products/CustomersProducts overlap inconsistent")

    governance = data.get("governance", {})
    require(governance.get("frozen_experiment_014_untouched") is True,
            "0.14 research boundary missing")
    require(governance.get("no_live_endpoint_or_credentials") is True,
            "unsafe live endpoint policy")
    require(governance.get("score_only_page_verified_actions") is True,
            "unverified customerOrders actions must not be scored as callable")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", nargs="?", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()
    errors = validate_inventory(json.loads(args.inventory.read_text(encoding="utf-8")))
    if errors:
        raise SystemExit("invalid ClicShopping source inventory:\n- " + "\n- ".join(errors))
    print("ClicShopping v4.33 public-source inventory verified (NOT SCORED).")


if __name__ == "__main__":
    main()

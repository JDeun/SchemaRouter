"""Build an unapproved, case-blind SafeAct V1 public-tool review queue.

Only consume official public IDs and the independent public template filename
inventory. This never reads case/evaluator gold, proposes policy requirements,
approves a contract, launches a model, or deduces the case's expected action.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.inventory_safeact_v1_public_tools import (
    PINNED_REVISION,
    PUBLIC_DOMAINS,
)
from scripts.prepare_safeact_v1_contract_review import review_worksheet

IDENT = re.compile(r"[a-z][a-z0-9_]*\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
POLICY_PATH = re.compile(
    r"templates/([a-z_]+)/world/policies/[a-z0-9_-]+"
    r"\.(?:md|json|txt|yaml|yml)\Z"
)


def build_review_queue(
    public_listing: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    """Generate a stable queue with blank human-only policy decisions."""
    worksheet = review_worksheet(public_listing)
    if (
        inventory.get("kind")
        != "safeact_v1_public_tool_filename_inventory_only"
        or inventory.get("upstream_revision") != PINNED_REVISION
        or inventory.get("human_reviewed") is not False
        or inventory.get("independently_authored_contracts") is not False
        or inventory.get("scored_experiment") is not False
        or inventory.get("policy_candidates_are_contracts") is not False
        or inventory.get("forbidden_sources_read") is not False
    ):
        raise ValueError("untrusted public inventory review boundary")
    tools = inventory.get("tools")
    policies = inventory.get("public_policy_candidates")
    if not isinstance(tools, list) or not tools:
        raise ValueError("public tool inventory is missing")
    if not isinstance(policies, list):
        raise ValueError("public policy inventory is missing")

    seen: set[tuple[str, str]] = set()
    items: list[dict[str, object]] = []
    allowed_domains = set(PUBLIC_DOMAINS)
    for entry in tools:
        if not isinstance(entry, dict):
            raise ValueError("public tool entry must be an object")
        domain, tool = entry.get("domain"), entry.get("tool_name")
        source, digest = entry.get("source_path"), entry.get("source_sha256")
        if (
            not isinstance(domain, str) or domain not in allowed_domains
            or not isinstance(tool, str) or not IDENT.fullmatch(tool)
            or source != f"templates/{domain}/tools/{tool}.py"
            or not isinstance(digest, str) or not SHA.fullmatch(digest)
        ):
            raise ValueError("invalid or non-public tool identity")
        identity = (domain, tool)
        if identity in seen:
            raise ValueError("duplicate domain-qualified public tool")
        seen.add(identity)
        items.append({
            "domain": domain,
            "tool": tool,
            "public_tool_source_path": source,
            "public_tool_sha256": digest,
            "consequential_action": None,
            "required_evidence": None,
            "observation_binding": None,
            "independent_policy_author": None,
            "independent_reviewer": None,
            "approved": False,
        })

    policy_records: list[dict[str, str]] = []
    policy_seen: set[str] = set()
    for entry in policies:
        if not isinstance(entry, dict):
            raise ValueError("public policy entry must be an object")
        domain, source = entry.get("domain"), entry.get("source_path")
        digest = entry.get("source_sha256")
        match = POLICY_PATH.fullmatch(source) if isinstance(source, str) else None
        if (
            not isinstance(domain, str) or domain not in allowed_domains
            or match is None or match.group(1) != domain
            or not isinstance(digest, str) or not SHA.fullmatch(digest)
        ):
            raise ValueError("invalid or non-public policy identity")
        if source in policy_seen:
            raise ValueError("duplicate public policy source")
        policy_seen.add(source)
        policy_records.append({
            "domain": domain,
            "source_path": source,
            "source_sha256": digest,
        })
    return {
        "schema_version": 1,
        "kind": "safeact_v1_case_blind_unreviewed_action_review_queue",
        "official_upstream_revision": PINNED_REVISION,
        "case_coverage": worksheet["case_coverage"],
        "case_ids_are_action_labels": False,
        "human_policy_author_reviewed": False,
        "independent_reviewer_approved": False,
        "scored_run_authorized": False,
        "model_calls": 0,
        "action_contracts": [],
        "public_tool_candidates": sorted(
            items, key=lambda x: (str(x["domain"]), str(x["tool"]))
        ),
        "unassigned_public_policy_candidates": sorted(
            policy_records, key=lambda x: x["source_path"]
        ),
        "review_note": (
            "Blank human review queue only. Tool names do not prove side effects,"
            " permitted actions, required evidence, or case-specific gold labels."
            " Independently write and review real domain-scoped contracts."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-listing", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    listing = json.loads(args.public_listing.read_text(encoding="utf-8"))
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    document = build_review_queue(listing, inventory)
    args.out.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(
        "Unreviewed public action candidates: "
        f"{len(document['public_tool_candidates'])}; "
        "131 opaque cohort IDs; NO contracts, reviews or model calls."
    )


if __name__ == "__main__":
    main()

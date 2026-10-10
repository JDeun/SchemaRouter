"""Validate a prospective ClicShopping confirmation submission without scoring."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from scripts.run_clicshopping_v433_dev import validate_cases
from scripts.validate_clicshopping_v433_inventory import COMMIT, validate_inventory


def check_confirmation(plan: dict, candidate: dict, dev: dict, inventory: dict) -> dict:
    if plan.get("status") != "prospective_unscored_no_heldout_cases":
        raise ValueError("confirmation must stay prospective")
    if plan.get("heldout_scoring_authorized") is not False:
        raise ValueError("unapproved confirmation cannot score")
    if plan.get("pinned_upstream") != COMMIT or validate_inventory(inventory):
        raise ValueError("pinned public upstream mismatch")
    if candidate.get("status") != "external_confirmation_unscored":
        raise ValueError("submitted cases must be unscored")
    if candidate.get("pinned_upstream_commit") != COMMIT:
        raise ValueError("submitted cases changed source revision")
    if candidate.get("roles") != dev.get("roles"):
        raise ValueError("permission roles changed")
    if candidate.get("protocol", {}).get("top_k") != plan["primary_top_k"]:
        raise ValueError("posthoc Top-K change not permitted")
    check = deepcopy(candidate)
    check["status"] = "preregistered_development_only_no_heldout_claim"
    validate_cases(check, inventory)
    existing_ids = {x["id"] for x in dev["cases"]}
    existing_texts = {" ".join(x["query"].casefold().split()) for x in dev["cases"]}
    new_ids = [x["id"] for x in candidate["cases"]]
    new_texts = [" ".join(x["query"].casefold().split()) for x in candidate["cases"]]
    if any(i in existing_ids or i.startswith("clic433-") for i in new_ids):
        raise ValueError("reuse of development case identifiers")
    if any(q in existing_texts for q in new_texts) or len(set(new_texts)) != len(new_texts):
        raise ValueError("reuse of development queries")
    # String disjointness alone cannot establish independent human authorship.
    digest = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
    return {"digest": digest, "cases": len(new_ids), "scoring_authorized": False,
            "independent_human_review_pending": True, "model_calls": 0}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    for name in ("plan", "candidate", "dev", "inventory"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    def read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(check_confirmation(read(args.plan), read(args.candidate),
                                        read(args.dev), read(args.inventory)),
                     sort_keys=True))


if __name__ == "__main__":
    main()

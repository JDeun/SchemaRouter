"""Validate a prospective ClicShopping confirmation submission without scoring."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from scripts.run_clicshopping_v433_dev import validate_cases
from scripts.validate_clicshopping_v433_inventory import COMMIT, validate_inventory


def _query_tokens(value: str) -> tuple[str, ...]:
    """Conservatively normalize punctuation and Unicode for reuse screening."""
    if not isinstance(value, str):
        raise ValueError("confirmation query must be text")
    return tuple(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def _overlaps_dev(candidate: tuple[str, ...], prior: tuple[str, ...]) -> bool:
    """Identify obvious dev copying; NEVER certify semantic independence."""
    if not candidate or not prior:
        return True
    candidate_text, prior_text = " ".join(candidate), " ".join(prior)
    if candidate_text == prior_text:
        return True
    # Append/prepend boilerplate and punctuation paraphrases are still copies.
    if len(prior) >= 3 and prior_text in candidate_text:
        return True
    if len(candidate) >= 3 and candidate_text in prior_text:
        return True
    # Reordering a nearly intact visible dev query is also contamination.
    old = set(prior)
    if len(old) >= 4 and len(old & set(candidate)) / len(old) >= 0.90:
        return True
    return False


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
    if candidate.get("protocol") != dev.get("protocol"):
        raise ValueError("confirmation protocol drift from frozen development setup")
    check = deepcopy(candidate)
    check["status"] = "preregistered_development_only_no_heldout_claim"
    validate_cases(check, inventory)
    existing_ids = {x["id"] for x in dev["cases"]}
    dev_tokens = [_query_tokens(x["query"]) for x in dev["cases"]]
    new_ids = [x["id"] for x in candidate["cases"]]
    new_tokens = [_query_tokens(x["query"]) for x in candidate["cases"]]
    if any(i in existing_ids or i.startswith("clic433-") for i in new_ids):
        raise ValueError("reuse of development case identifiers")
    if len(set(new_tokens)) != len(new_tokens):
        raise ValueError("reuse of development queries")
    if any(
        _overlaps_dev(query, original)
        for query in new_tokens
        for original in dev_tokens
    ):
        raise ValueError("reuse of development queries: contaminated wording")
    # This is only an inexpensive warning barrier, not a semantic plagiarism
    # detector. Case/label meanings need blinded independent human review.
    # Structural non-reuse cannot establish independent human authorship.
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

"""Validate V6H DEV governance invariants and artifact retention policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    policy = data["policy"]
    metrics = data["metrics"]

    required_false = (
        "confirmation_scored",
        "positive_rerank",
        "endpoint_switch",
        "rank2_fallback",
        "pseudo_route",
        "validation_split",
        "early_stopping",
        "dev_selected_hyperparameters",
    )
    for key in required_false:
        if policy[key]:
            raise SystemExit(f"forbidden policy enabled: {key}")

    if not policy["raw_bge_is_sole_positive_selector"]:
        raise SystemExit("positive route authority changed")
    if not policy["parser_veto_only"]:
        raise SystemExit("parser gained positive authority")
    if policy["probability_threshold"] is not None:
        raise SystemExit("probability threshold detected")
    if policy["margin_threshold"] is not None:
        raise SystemExit("margin threshold detected")

    for key in (
        "positive_route_switches",
        "authority_violations",
        "execution_errors",
    ):
        if metrics[key] != 0:
            raise SystemExit(f"governance/runtime invariant failed: {key}")

    if not data["quality_pass"] and args.state.exists():
        args.state.unlink()
        print("DEV quality failed; trained state removed from artifact")
    else:
        print("quality passed; exact trained state retained")

    print("quality_pass=", data["quality_pass"])
    print("runtime_gate=", data["runtime_gate"])
    print("surface_pass=", data["surface_pass"])


if __name__ == "__main__":
    main()

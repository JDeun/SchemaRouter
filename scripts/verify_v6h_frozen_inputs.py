"""Verify frozen V6H corpus and training-bank identities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--bank-sha256", required=True)
    parser.add_argument("--dev-sha256", required=True)
    parser.add_argument("--confirm-sha256", required=True)
    args = parser.parse_args()

    freeze = json.loads(
        (args.root / "freeze-manifest.json").read_text(encoding="utf-8")
    )
    if freeze["development"]["corpus_sha256"] != args.dev_sha256:
        raise SystemExit("DEV corpus identity drifted")
    if freeze["confirmation"]["corpus_sha256"] != args.confirm_sha256:
        raise SystemExit("confirmation corpus identity drifted")
    if hashlib.sha256(args.bank.read_bytes()).hexdigest() != args.bank_sha256:
        raise SystemExit("training bank identity drifted")

    for role in ("development", "confirmation"):
        manifest = freeze[role]
        expected = {
            "case_count": 552,
            "supported_cases": 228,
            "near_domain_cases": 252,
            "out_of_domain_cases": 72,
            "route_count": 19,
            "tool_count": 7,
        }
        for key, value in expected.items():
            if manifest[key] != value:
                raise SystemExit(f"unexpected {role} {key}: {manifest[key]}")
        if manifest["endpoint_counts"] != [2, 2, 3, 3, 3, 3, 3]:
            raise SystemExit(f"unexpected {role} endpoint counts")
        if manifest["training_bank_sha256"] != args.bank_sha256:
            raise SystemExit(f"unexpected {role} training-bank provenance")

    print("V6H identities verified; confirmation remains unscored")


if __name__ == "__main__":
    main()

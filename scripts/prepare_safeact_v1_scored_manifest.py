"""Prepare an explicitly UNAPPROVED SafeAct V1 scored-run manifest.

This tool helps independently reviewed contracts reach reproducible GitHub
Actions execution. It NEVER signs an evidence contract, grants review, calls
models, reads evaluator gold, or authorizes scored model execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path

from examples.external_validation.safeact_v1.run_plan import CONDITIONS
from scripts.run_safeact_v1_scored import UPSTREAM_REVISION

EXPECTED_CONTRACT_RELATIVE = Path("research/safeact-v1/contracts.json")


def canonical_digest(document: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            document, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_unreviewed_manifest(
    contract: dict,
    *,
    model: str,
    backend: str,
    adapter_commit: str,
) -> dict:
    if not isinstance(contract, dict):
        raise ValueError("contract document must be an object")
    if not model or not model.strip() or any(c in model for c in "\r\n"):
        raise ValueError("frozen model identity required")
    if backend not in {"codex", "claude"}:
        raise ValueError("official backend must be codex or claude")
    if not re.fullmatch(r"[a-f0-9]{40}", adapter_commit):
        raise ValueError("adapter commit must be a frozen Git SHA")
    digest = canonical_digest(contract)
    options = (
        f"--backend {backend} --model {shlex.quote(model)} "
        "--strategy baseline"
    )
    base = "python3 @SAFEACT_ROOT@/agents/coding_cli_safeact_agent.py"
    router = (
        "python3 @SCHEMAROUTER_ROOT@/examples/external_validation/"
        "safeact_v1/official_routing_hook.py --condition routing_only"
    )
    gate = (
        "python3 @SCHEMAROUTER_ROOT@/examples/external_validation/"
        "safeact_v1/official_agent_hook.py --condition evidence_gate "
        "--contract-file @SCHEMAROUTER_ROOT@/research/safeact-v1/contracts.json "
        f"--contract-sha256 {digest} "
        "--public-source-root "
        "@SCHEMAROUTER_ROOT@/research/safeact-v1/public-sources"
    )
    commands = (f"{base} {options}", f"{router} {options}", f"{gate} {options}")
    modes = ("ungated", "routing_only", "evidence_gate")
    return {
        "schema_version": 1,
        "research": "safeact-v1-scored-393",
        "official_upstream_revision": UPSTREAM_REVISION,
        "contract_sha256": digest,
        "reviewed": False,
        "independent_contract_review": {
            "approved": False,
            "author": "",
            "reviewer": "",
            "contract_sha256": digest,
            "upstream_revision": UPSTREAM_REVISION,
        },
        "conditions": {
            condition: {
                "mode": mode,
                "adapter_commit": adapter_commit,
                "agent_command": command,
                "agent_command_sha256": hashlib.sha256(
                    command.encode("utf-8")
                ).hexdigest(),
            }
            for condition, mode, command in zip(
                CONDITIONS, modes, commands, strict=True
            )
        },
        "review_note": (
            "DRAFT ONLY. Human policy-author and different independent "
            "reviewer must assess sources, mapping of all 131 cases, "
            "adapter fidelity and model environment before signing. "
            "Never flip review fields solely to get a successful run."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--backend", choices=["codex", "claude"], required=True)
    parser.add_argument("--adapter-commit", required=True)
    args = parser.parse_args()

    # The GitHub workflow reads exactly these frozen paths. Do not silently
    # write an approved-looking substitute somewhere else.
    if args.contracts != EXPECTED_CONTRACT_RELATIVE:
        raise ValueError("contracts path must match scored workflow input")
    if args.out != Path("research/safeact-v1/intervention-manifest.json"):
        raise ValueError("manifest output must match scored workflow input")
    document = json.loads(args.contracts.read_text(encoding="utf-8"))
    result = build_unreviewed_manifest(
        document, model=args.model, backend=args.backend,
        adapter_commit=args.adapter_commit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Wrote unapproved frozen manifest skeleton; "
        "scored launch remains blocked pending real independent review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

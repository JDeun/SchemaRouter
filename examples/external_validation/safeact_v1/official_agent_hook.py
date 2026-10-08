"""Trusted parent-side hook into the PINNED official SafeAct V1 CLI adapter.

Never import SafeAct evaluator/gold documents here. The official adapter owns
the actual tool gateway; this hook only receives gateway.calls that were
observed before an agent's consequential proposal and the public scenario.
"""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Invoked by SafeAct from its own workspace; the SchemaRouter source root
# must be resolved independently of cwd before importing the trusted package.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from examples.external_validation.safeact_v1.record_intervention import (
    gate_official_v1_record,
)
from examples.external_validation.safeact_v1.trusted_session import (
    VerifiedToolEvidence,
)
from scripts.verify_safeact_v1_sources import verify_sources

PINNED_SAFEACT_SHA = "841816cf1e376e6fbf8600cffac5df1736e1d369"


def strict_public_evidence(
    tool: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    *,
    mapping: dict[str, Any],
) -> VerifiedToolEvidence | None:
    """Credit only a unique, actual, structured public tool observation.

    The extraction field names must be pinned by an independent contract.
    No evaluator fields, gold labels or hidden case specs are inspected.
    """
    spec = mapping.get(tool)
    if not isinstance(spec, dict):
        return None
    entity_key = spec.get("record_id_key")
    field_key = spec.get("field_name_key")
    if (
        not isinstance(entity_key, str)
        or not entity_key.isidentifier()
        or not isinstance(field_key, str)
        or not field_key.isidentifier()
    ):
        raise ValueError("independent public observation mapping is malformed")
    if result.get("status") != "ok" or result.get("tool") != tool:
        return None
    if not isinstance(result.get("call_id"), str):
        return None
    observed = result.get("observations")
    if not isinstance(observed, list) or not observed:
        return None
    ids: set[str] = set()
    fields: set[str] = set()
    for fact in observed:
        if not isinstance(fact, dict):
            return None
        record = fact.get(entity_key)
        field = fact.get(field_key)
        if (
            not isinstance(record, str)
            or not record
            or not isinstance(field, str)
            or not field
        ):
            return None
        ids.add(record)
        fields.add(field)
    if len(ids) != 1:
        return None
    return VerifiedToolEvidence(record_id=next(iter(ids)), fields=frozenset(fields))


def install_v1_gate(
    official_module: Any, *, document: dict, source_root: Path, case_id: str
) -> None:
    """Patch the official host-side normalized V1 record commit point.

    The upstream CLI controls both model isolation and the trustworthy
    ToolGateway. The adapter captures only its public completed-call records.
    """
    verified_errors = verify_sources(document, source_root)
    if verified_errors:
        raise ValueError("independent contract preflight failed: " + "; ".join(verified_errors))
    if case_id not in document.get("case_coverage", {}):
        raise ValueError("public V1 case has no independent contract coverage")
    existing_init = official_module.ToolGateway.__init__
    original_normalize = official_module.normalize_v1
    gateways: list[Any] = []

    def capture_gateway(instance: Any, *args: Any, **kwargs: Any) -> None:
        existing_init(instance, *args, **kwargs)
        gateways.append(instance)

    def normalize_with_gate(
        scenario: dict,
        parsed: dict,
        info_events: list,
        backend: str,
        model: str | None,
        raw: str,
        error: str | None,
    ) -> dict:
        result = original_normalize(
            scenario, parsed, info_events, backend, model, raw, error
        )
        if len(gateways) != 1:
            raise ValueError("one isolated trusted V1 gateway required")
        gateway = gateways[0]
        if gateway.protocol != "v1":
            raise ValueError("trusted record gate is restricted to official V1")
        mapping = document.get("public_observation_mappings")
        if not isinstance(mapping, dict):
            raise ValueError("independent public observation mappings required")
        return gate_official_v1_record(
            result,
            case_id=case_id,
            contract_document=document,
            public_source_root=source_root,
            actual_gateway_calls=gateway.calls,
            verify_result=lambda tool, args, output: strict_public_evidence(
                tool, args, output, mapping=mapping
            ),
        )

    official_module.ToolGateway.__init__ = capture_gateway
    official_module.normalize_v1 = normalize_with_gate


def require_baseline_strategy(
    upstream_args: list[str], *, environment: Mapping[str, str]
) -> None:
    """Disallow agent-strategy confounds across all SafeAct V1 arms.

    The pinned upstream CLI defaults its strategy from the environment and
    accepts both spaced and equals-form flags. Both must be controlled before
    any official model call; a hidden SCGR strategy would invalidate the
    intervention-only three-arm comparison.
    """
    if environment.get("SAFEACT_AGENT_STRATEGY", "baseline") != "baseline":
        raise ValueError("upstream environment strategy must remain baseline")
    found: list[str] = []
    for index, token in enumerate(upstream_args):
        if token == "--strategy":
            if index + 1 >= len(upstream_args):
                raise ValueError("upstream strategy requires an argument")
            found.append(upstream_args[index + 1])
        elif token.startswith("--strategy="):
            found.append(token.partition("=")[2])
    if len(found) > 1 or any(value != "baseline" for value in found):
        raise ValueError("upstream agent strategy confounds comparison")


def find_official_root(workspace: Path) -> Path:
    for candidate in (workspace, *workspace.parents):
        path = candidate / "agents" / "coding_cli_safeact_agent.py"
        if path.is_file() and not path.is_symlink():
            return candidate
    raise ValueError("official SafeAct source root not found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-file", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--public-source-root", type=Path, required=True)
    parser.add_argument("--condition", choices=["evidence_gate"], required=True)
    args, upstream_args = parser.parse_known_args()

    # CLI arguments are parent-authored, never copied from agent response.
    case_id = os.environ.get("SAFEACT_CASE_ID")
    if not isinstance(case_id, str) or not case_id.startswith("SAB-V1-"):
        raise ValueError("missing trusted SafeAct V1 case identity")
    root = find_official_root(Path.cwd().resolve())
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if revision != PINNED_SAFEACT_SHA:
        raise ValueError("unverified upstream SafeAct revision")
    require_baseline_strategy(upstream_args, environment=os.environ)
    if not any(
        token == "--model" or token.startswith("--model=")
        for token in upstream_args
    ):
        raise ValueError("explicit frozen runtime model required")
    module_path = root / "agents" / "coding_cli_safeact_agent.py"
    document = json.loads(args.contract_file.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("independent contract document must be an object")
    digest = hashlib.sha256(
        json.dumps(
            document, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if digest != args.contract_sha256:
        raise ValueError("frozen independent contract hash mismatch")
    spec = importlib.util.spec_from_file_location("safeact_official_v1", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("official V1 adapter import failed")
    sys.path.insert(0, str(root / "agents"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    install_v1_gate(
        module, document=document,
        source_root=args.public_source_root.resolve(strict=True),
        case_id=case_id,
    )
    # The official CLI parses only its own arguments, with original isolation.
    sys.argv = [str(module_path), *upstream_args]
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())

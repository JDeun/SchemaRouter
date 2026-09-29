"""Generate deterministic capability-conditioned intent manuals for #434.

This generator consumes only frozen capability catalogs.  It never reads DEV/confirmation
queries, task IDs, gold routes, B1 results, or retrieval outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v2_catalog import CATALOG_SIZES  # noqa: E402
from schemarouter import ToolSpec  # noqa: E402

AMENDMENT_PATH = (
    ROOT / "benchmarks" / "agent-utility-v2-intent-manual-amendment.json"
)
GENERATOR_REVISION = "deterministic-capability-intent-manual-v1"
_WS_RE = re.compile(r"\s+")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _normalize_for_dedup(text: str) -> str:
    return _WS_RE.sub(" ", text.strip()).casefold()


def _join_nonempty(values: list[str | None]) -> str:
    return " ".join(value.strip() for value in values if value and value.strip())


def _output_phrase(endpoint: Any) -> str:
    parts: list[str] = []
    for field in endpoint.output_fields:
        field_parts = [
            field.description or field.name,
            field.semantic_id,
        ]
        if field.json_schema:
            declared = field.json_schema.get("type")
            if isinstance(declared, str):
                field_parts.append(f"type {declared}")
        if field.unit:
            field_parts.append(f"unit {field.unit}")
        if field.unit_normalization is not None:
            field_parts.append(
                f"dimension {field.unit_normalization.dimension}"
            )
            field_parts.append(
                f"canonical unit {field.unit_normalization.canonical_unit}"
            )
        parts.append(_join_nonempty(field_parts))
    return "; ".join(part for part in parts if part)


def _input_phrase(endpoint: Any) -> str:
    parts: list[str] = []
    for parameter in endpoint.parameters:
        requirement = "required" if parameter.required else "optional"
        parts.append(
            _join_nonempty(
                [
                    parameter.description or parameter.name,
                    f"parameter {parameter.name}",
                    requirement,
                ]
            )
        )
    return "; ".join(part for part in parts if part)


def _policy_phrase(tool: ToolSpec, endpoint: Any) -> str:
    identity = f"{tool.key}.{endpoint.name}"
    if endpoint.destructive:
        return (
            f"Permanently perform {endpoint.name} with {identity}; "
            "this is a destructive state-changing action."
        )
    if endpoint.read_only:
        return (
            f"Read or inspect data with {identity} without changing state."
        )
    return f"Change application state with {identity} using a non-destructive write action."


def generate_manual_for_tool(tool: ToolSpec) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for endpoint in sorted(tool.endpoints, key=lambda item: item.name):
        route_id = f"{tool.key}.{endpoint.name}"
        action = _join_nonempty(
            [
                f"Use {tool.key}.{endpoint.name}.",
                tool.description,
                endpoint.description,
            ]
        )
        output = _output_phrase(endpoint)
        output_need = (
            _join_nonempty(
                [
                    "I need the declared result:",
                    output,
                    f"Use {route_id}.",
                ]
            )
            if output
            else ""
        )
        inputs = _input_phrase(endpoint)
        input_to_output = (
            _join_nonempty(
                [
                    f"Given {inputs},",
                    endpoint.description,
                    f"Use {route_id}.",
                ]
            )
            if inputs
            else ""
        )
        policy = _policy_phrase(tool, endpoint)

        candidates = [
            ("capability_action", action),
            ("output_need", output_need),
            ("input_to_output", input_to_output),
            ("policy_sensitive_action", policy),
        ]
        seen: set[str] = set()
        intents: list[dict[str, str]] = []
        for template, text in candidates:
            normalized = _normalize_for_dedup(text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            intents.append(
                {
                    "template": template,
                    "text": _WS_RE.sub(" ", text.strip()),
                }
            )

        if not intents:
            raise RuntimeError(f"intent generation produced no text for {route_id}")

        rows.append(
            {
                "route_id": route_id,
                "tool_fingerprint": tool.fingerprint,
                "endpoint_fingerprint": endpoint.fingerprint,
                "generator_revision": GENERATOR_REVISION,
                "intents": intents,
            }
        )
    return rows


def generate_for_catalog(
    catalog_path: Path,
    *,
    source_catalog_sha256: str,
) -> dict[str, Any]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    tools = [
        ToolSpec.model_validate(row)
        for row in payload
    ]
    rows = [
        row
        for tool in sorted(tools, key=lambda item: item.key)
        for row in generate_manual_for_tool(tool)
    ]
    endpoint_count = sum(len(tool.endpoints) for tool in tools)
    if len(rows) != endpoint_count:
        raise RuntimeError(
            "intent-manual row count must equal registered endpoint count"
        )
    return {
        "schema_version": 1,
        "issue": 434,
        "generator_revision": GENERATOR_REVISION,
        "source_catalog_sha256": source_catalog_sha256,
        "source_catalog_file_sha256": _file_sha(catalog_path),
        "endpoint_count": endpoint_count,
        "rows": rows,
        "rows_sha256": _sha(rows),
    }


def generate_all(freeze_dir: Path, out_dir: Path) -> dict[str, Any]:
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    if amendment["status"] != "frozen_before_intent_manual_dev_scoring":
        raise RuntimeError("intent-manual amendment is not frozen")
    if amendment["generator"]["revision"] != GENERATOR_REVISION:
        raise RuntimeError("intent-manual generator revision drifted")
    if amendment["evaluation"]["confirmation_allowed"] is not False:
        raise RuntimeError("confirmation must remain blocked")

    freeze = json.loads(
        (freeze_dir / "freeze-manifest.json").read_text(encoding="utf-8")
    )
    if freeze.get("surface") != "development":
        raise RuntimeError("intent-manual DEV generation requires DEV freeze")
    if freeze.get("confirmation_surface_opened") is not False:
        raise RuntimeError("confirmation surface must remain sealed")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "issue": 434,
        "surface": "development",
        "confirmation_surface_opened": False,
        "generator_revision": GENERATOR_REVISION,
        "amendment_path": str(AMENDMENT_PATH.relative_to(ROOT)),
        "amendment_sha256": _file_sha(AMENDMENT_PATH),
        "catalogs": {},
    }

    for size in CATALOG_SIZES:
        source = freeze["catalogs"][str(size)]["sha256"]
        generated = generate_for_catalog(
            freeze_dir / f"catalog-{size}.json",
            source_catalog_sha256=source,
        )
        path = out_dir / f"intent-manual-{size}.json"
        path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["catalogs"][str(size)] = {
            "endpoint_count": generated["endpoint_count"],
            "source_catalog_sha256": source,
            "rows_sha256": generated["rows_sha256"],
            "file_sha256": _file_sha(path),
        }

    (out_dir / "intent-manual-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--surface",
        choices=("development", "confirmation"),
        default="development",
    )
    args = parser.parse_args()

    if args.surface == "confirmation":
        raise SystemExit(
            "confirmation intent-manual generation is sealed until a DEV candidate "
            "is frozen under #434"
        )

    manifest = generate_all(args.freeze_dir, args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

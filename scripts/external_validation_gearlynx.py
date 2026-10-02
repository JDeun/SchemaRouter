"""Frozen Gearlynx MCP-router cross-benchmark.

Gearlynx remains authoritative for tool schemas, validation, and execution.
This benchmark compares only candidate discovery/disclosure against a frozen,
derived catalog from drhelius/Gearlynx.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from schemarouter import EndpointSpec, ParameterSpec, SchemaRouter, ToolSpec

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/external_validation/gearlynx-router/catalog.json"

CASES: tuple[tuple[str, str | None], ...] = (
    ("suzy registers", "get_suzy_registers"),
    ("uart status", "get_uart_status"),
    ("memory search", "memory_search"),
    ("memory watches", "list_memory_watches"),
    ("symbol lookup name", "lookup_symbol_by_name"),
    ("trace log", "get_trace_log"),
    ("rewind status", "get_rewind_status"),
    ("save state slots", "list_save_state_slots"),
    ("cartridge status", "get_cart_status"),
    ("lcd status", "get_lcd_status"),
    ("sprite metadata", "get_sprite"),
    ("input state", "get_input_state"),
    ("network socket", None),
    ("database sql", None),
    ("email inbox", None),
    ("weather forecast", None),
)

TOKEN_RE = re.compile(r"[a-z0-9]+")


def load_catalog() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def native_search(query: str, tools: list[dict[str, Any]], limit: int = 20) -> list[str]:
    """Mirror Gearlynx SearchTools: case-insensitive AND substring search."""
    terms = query.casefold().split()
    if not terms:
        return []
    out: list[str] = []
    for tool in tools:
        aliases = tool["category"]
        name = tool["name"]
        if "mikey" in name:
            aliases += " timers timer irq interrupt hblank vblank audio uart comlynx"
        if "suzy" in name or "sprite" in name:
            aliases += " sprites sprite blitter math collision scb"
        if "lcd" in name:
            aliases += " video display scanline hblank vblank palette tiles background"
        if "breakpoint" in name:
            aliases += " watchpoint stop read write execute irq interrupt"
        if "memory" in name:
            aliases += " ram rom vram bytes search watch bookmark selection"
        if "symbol" in name:
            aliases += " label labels names debug symbols"
        if "trace" in name:
            aliases += " log logger events cpu irq debug output"
        if "controller" in name:
            aliases += " input joypad gamepad button macro tap press release"
        if "state" in name or "rewind" in name:
            aliases += " save savestate slot snapshot time travel history"
        if "cart" in name or "eeprom" in name:
            aliases += " cartridge rom mapper bank save nonvolatile"
        haystack = " ".join(
            [name, tool["title"], tool["description"], tool["category"], aliases]
        ).casefold()
        if all(term in haystack for term in terms):
            out.append(name)
            if len(out) >= limit:
                break
    return out


def build_router(tools: list[dict[str, Any]]) -> SchemaRouter:
    router = SchemaRouter()
    for tool in tools:
        params = [
            ParameterSpec(name=name, required=False, json_schema={"type": "string"})
            for name in tool["parameter_names"]
        ]
        router.add_tool(
            ToolSpec(
                name=tool["name"],
                description=" ".join(
                    [tool["title"], tool["description"], "category", tool["category"]]
                ),
                provider="gearlynx",
                access_mode="mcp-router-mirror",
                remote=False,
                endpoints=[
                    EndpointSpec(
                        name="invoke",
                        description=tool["description"],
                        parameters=params,
                        read_only=True,
                        destructive=False,
                    )
                ],
            )
        )
    return router


def schemarouter_search(
    router: SchemaRouter, query: str, allowed: set[str], limit: int = 3
) -> list[str]:
    retrieval = router.retrieve(query, k=max(limit, 1))
    query_tokens = set(TOKEN_RE.findall(query.casefold()))
    selected: list[str] = []
    for candidate in retrieval.candidates:
        if candidate.tool not in allowed:
            continue
        identifier_tokens = set(TOKEN_RE.findall(candidate.tool.casefold()))
        evidence_tokens = {
            component.matched.casefold()
            for component in candidate.score_components
            if component.kind == "tool_token"
        }
        if not (query_tokens & identifier_tokens & evidence_tokens):
            continue
        selected.append(candidate.tool)
        if len(selected) >= limit:
            break
    return selected


def _summary(rows: list[dict[str, Any]], prefix: str) -> dict[str, float]:
    supported = [r for r in rows if r["required_tool"] is not None]
    unsupported = [r for r in rows if r["required_tool"] is None]
    return {
        "required_tool_recall": sum(
            r["required_tool"] in r[f"{prefix}_selected"] for r in supported
        ) / len(supported),
        "unsupported_rejection": sum(
            not r[f"{prefix}_selected"] for r in unsupported
        ) / len(unsupported),
        "mean_selected_tools": statistics.mean(
            len(r[f"{prefix}_selected"]) for r in rows
        ),
        "mean_schema_source_bytes": statistics.mean(
            r[f"{prefix}_schema_source_bytes"] for r in rows
        ),
        "mean_latency_ms": statistics.mean(r[f"{prefix}_latency_ms"] for r in rows),
    }


def evaluate() -> dict[str, Any]:
    fixture = load_catalog()
    tools = fixture["tools"]
    allowed = {tool["name"] for tool in tools}
    router = build_router(tools)
    tool_by_name = {tool["name"]: tool for tool in tools}
    rows: list[dict[str, Any]] = []

    for query, required in CASES:
        started = time.perf_counter()
        native = native_search(query, tools)
        native_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        routed = schemarouter_search(router, query, allowed)
        routed_ms = (time.perf_counter() - started) * 1000

        native_schema_source_bytes = sum(
            tool_by_name[name]["schema_source_bytes"] for name in native
        )
        schemarouter_schema_source_bytes = sum(
            tool_by_name[name]["schema_source_bytes"] for name in routed
        )

        rows.append(
            {
                "query": query,
                "required_tool": required,
                "native_selected": native,
                "schemarouter_selected": routed,
                "native_latency_ms": round(native_ms, 6),
                "schemarouter_latency_ms": round(routed_ms, 6),
                "native_schema_source_bytes": native_schema_source_bytes,
                "schemarouter_schema_source_bytes": schemarouter_schema_source_bytes,
            }
        )

    direct = [tool for tool in tools if tool["direct"]]
    routed_tools = [tool for tool in tools if not tool["direct"]]
    full_schema_source_bytes = sum(tool["schema_source_bytes"] for tool in tools)
    routed_schema_source_bytes = sum(tool["schema_source_bytes"] for tool in routed_tools)

    return {
        "schema_version": 1,
        "integration": "gearlynx-mcp-router",
        "evidence_level": "E1-maintainer-accepted-benchmark",
        "upstream": fixture["upstream"],
        "boundary": {
            "schemarouter_role": "candidate selection only",
            "gearlynx_role": "authoritative catalog, schema, validation, execution",
            "execution_through_schemarouter": False,
        },
        "catalog": {
            "tool_count": len(tools),
            "direct_tool_count": len(direct),
            "routed_tool_count": len(routed_tools),
            "full_schema_source_bytes": full_schema_source_bytes,
            "routed_schema_source_bytes": routed_schema_source_bytes,
            "note": (
                "schema_source_bytes measures frozen C++ inputSchema initializer source, "
                "not wire JSON bytes"
            ),
        },
        "field_recall": {
            "status": "not_reported",
            "reason": (
                "The pinned Gearlynx catalog does not expose normalized output-field labels; "
                "no field labels are imputed."
            ),
        },
        "native_summary": _summary(rows, "native"),
        "schemarouter_summary": _summary(rows, "schemarouter"),
        "cases": rows,
        "known_limits": [
            "Phase A is retrieval-only and does not claim emulator task success.",
            "The fixture is derived from a pinned upstream source commit.",
            (
                "Required-field recall is not reported because the frozen upstream metadata "
                "does not provide normalized output-field labels."
            ),
            (
                "Parameter schemas are not reimplemented in SchemaRouter; "
                "Gearlynx remains authoritative."
            ),
            (
                "Native search mirrors Gearlynx AND-substring search and alias rules for "
                "Gearlynx-relevant names."
            ),
            "The frozen case set is maintainer-owned E1 evidence, not independent E2 validation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = evaluate()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

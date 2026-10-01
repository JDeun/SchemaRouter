"""mcp-agent catalog retrieval composition evaluation.

mcp-agent owns MCPApp, Agent, connection/session lifecycle, and tool filtering.
SchemaRouter mirrors discovered tool schemas for retrieval only and supplies the
allowed bare tool names passed back to Agent.list_tools(tool_filter=...).
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import statistics
import sys
import tempfile
import time
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mcp.types import Tool
from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp
from mcp_agent.config import MCPServerSettings, MCPSettings, Settings

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec

SERVER_NAME = "validation"
SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "external_validation"
    / "openai_agents_mcp_filter"
    / "server.py"
)
_IDENTIFIER_TOKEN_RE = re.compile(r"[a-z0-9]+")

CASES: tuple[dict[str, Any], ...] = (
    {
        "query": "current weather in Seoul",
        "required_tools": ("weather_lookup",),
    },
    {
        "query": "find a hotel and restaurant in Seoul",
        "required_tools": ("hotel_search", "restaurant_search"),
    },
    {
        "query": "electronic band gap for silicon",
        "required_tools": ("material_band_gap",),
    },
    {
        "query": "delete an archived record",
        "required_tools": ("delete_record",),
        "sensitive": True,
    },
    {
        "query": "compose a string quartet with counterpoint and harmony",
        "required_tools": (),
    },
)


def _assert_installed_wheel() -> None:
    package_file = Path(inspect.getfile(SchemaRouter)).resolve()
    repository_root = Path(__file__).resolve().parents[1]
    assert repository_root not in package_file.parents, package_file
    assert "site-packages" in package_file.parts, package_file


def _input_schema(tool: Tool) -> dict[str, Any]:
    value = getattr(tool, "inputSchema", None)
    if isinstance(value, dict):
        return deepcopy(value)
    value = getattr(tool, "input_schema", None)
    return deepcopy(value) if isinstance(value, dict) else {}


def _output_schema(tool: Tool) -> dict[str, Any]:
    value = getattr(tool, "outputSchema", None)
    if isinstance(value, dict):
        return deepcopy(value)
    value = getattr(tool, "output_schema", None)
    return deepcopy(value) if isinstance(value, dict) else {}


def _annotations(tool: Tool) -> dict[str, Any]:
    value = getattr(tool, "annotations", None)
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json", exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _optional_raw_metadata(tool: Tool) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for attr in ("title", "icons", "meta", "_meta"):
        value = getattr(tool, attr, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", exclude_none=True)
        elif isinstance(value, list):
            value = [
                item.model_dump(mode="json", exclude_none=True)
                if hasattr(item, "model_dump")
                else item
                for item in value
            ]
        payload[attr] = value
    annotations = _annotations(tool)
    if annotations:
        payload["annotations"] = annotations
    return payload


def _annotation_bool(
    annotations: dict[str, Any],
    camel: str,
    snake: str,
) -> bool | None:
    value = annotations.get(camel, annotations.get(snake))
    return value if isinstance(value, bool) else None


def _bare_name(namespaced: str) -> str:
    prefix = f"{SERVER_NAME}_"
    if not namespaced.startswith(prefix):
        raise AssertionError(
            f"expected mcp-agent namespaced tool prefix {prefix!r}: {namespaced!r}"
        )
    return namespaced[len(prefix) :]


def _register_retrieval_mirror(
    router: SchemaRouter,
    discovered: list[Tool],
) -> dict[str, str]:
    bare_to_namespaced: dict[str, str] = {}
    for tool in discovered:
        bare = _bare_name(tool.name)
        annotations = _annotations(tool)
        read_only = _annotation_bool(annotations, "readOnlyHint", "read_only_hint")
        destructive = _annotation_bool(
            annotations,
            "destructiveHint",
            "destructive_hint",
        )

        endpoint = EndpointSpec(
            name="invoke",
            description=tool.description or "",
            input_schema=_input_schema(tool),
            output_schema=_output_schema(tool),
            read_only=read_only,
            destructive=destructive,
            metadata={
                "mcp_agent_source": {
                    "server_name": SERVER_NAME,
                    "namespaced_tool_name": tool.name,
                    "raw_optional_metadata": _optional_raw_metadata(tool),
                }
            },
        )
        router.add_tool(
            ToolSpec(
                name=bare,
                description=tool.description or "",
                provider="mcp-agent",
                access_mode="mcp-agent-tool-filter-mirror",
                source_type="mcp",
                remote=True,
                endpoints=[endpoint],
            )
        )
        bare_to_namespaced[bare] = tool.name
    return bare_to_namespaced


class SchemaRouterCatalogSelector:
    """Bounded retrieval selector for mcp-agent's native tool_filter."""

    def __init__(self, router: SchemaRouter, *, max_results: int = 4) -> None:
        self.router = router
        self.max_results = max_results
        self.evidence: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _identifier_tokens(value: str) -> set[str]:
        return set(_IDENTIFIER_TOKEN_RE.findall(value.casefold()))

    @classmethod
    def _has_disclosure_signal(cls, candidate: Any) -> bool:
        identifier_tokens = cls._identifier_tokens(candidate.tool)
        for component in candidate.score_components:
            matched = component.matched
            if component.kind in {"preferred_tool", "preferred_endpoint"}:
                return True
            if (
                component.kind == "tool_token"
                and isinstance(matched, str)
                and matched.casefold() in identifier_tokens
            ):
                return True
        return False

    def select(self, query: str) -> set[str]:
        started = time.perf_counter()
        retrieval = self.router.retrieve(query, k=self.max_results)
        selected: list[str] = []
        evidence: list[dict[str, Any]] = []
        for candidate in retrieval.candidates:
            signal = self._has_disclosure_signal(candidate)
            evidence.append(
                {
                    "tool": candidate.tool,
                    "score": candidate.score,
                    "disclosure_signal": signal,
                    "score_components": [
                        component.model_dump(mode="json")
                        for component in candidate.score_components
                    ],
                }
            )
            if signal and candidate.tool not in selected:
                selected.append(candidate.tool)
            if len(selected) >= self.max_results:
                break

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.evidence[query] = {
            "selected_tools": selected,
            "routing_latency_ms": round(elapsed_ms, 6),
            "candidates": evidence,
        }
        return set(selected)


def _serialized_tool_bytes(tools: list[Tool]) -> int:
    payload = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": _input_schema(tool),
            "output_schema": _output_schema(tool),
            "annotations": _annotations(tool),
        }
        for tool in tools
    ]
    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _typed_promotion_omissions(tool: Tool) -> list[str]:
    annotations = _annotations(tool)
    omitted: list[str] = []
    for camel, snake in (
        ("idempotentHint", "idempotent_hint"),
        ("openWorldHint", "open_world_hint"),
        ("title", "title"),
    ):
        value = annotations.get(camel, annotations.get(snake))
        if value is not None:
            omitted.append(f"annotations.{camel}")

    raw = _optional_raw_metadata(tool)
    for field in ("title", "icons", "meta", "_meta"):
        if field in raw:
            omitted.append(field)
    return sorted(set(omitted))


def _settings(call_log: Path) -> Settings:
    return Settings(
        execution_engine="asyncio",
        mcp=MCPSettings(
            servers={
                SERVER_NAME: MCPServerSettings(
                    transport="stdio",
                    command=sys.executable,
                    args=[str(SERVER_PATH)],
                    cwd=str(SERVER_PATH.parents[3]),
                    env={
                        "SCHEMAROUTER_OPENAI_AGENTS_CALL_LOG": str(call_log),
                    },
                )
            }
        ),
    )


async def evaluate() -> dict[str, Any]:
    _assert_installed_wheel()

    with tempfile.TemporaryDirectory(prefix="schemarouter-mcp-agent-") as tmp:
        call_log = Path(tmp) / "tool-calls.jsonl"
        app = MCPApp(
            name="schemarouter-mcp-agent-validation",
            settings=_settings(call_log),
        )

        async with app.run():
            agent = Agent(
                name="catalog-validation",
                instruction="Validation-only agent; no LLM or tool call is performed.",
                server_names=[SERVER_NAME],
                connection_persistence=True,
                context=app.context,
            )

            async with agent:
                full_result = await agent.list_tools()
                discovered = list(full_result.tools)
                assert len(discovered) >= 10, len(discovered)

                router = SchemaRouter()
                bare_to_namespaced = _register_retrieval_mirror(router, discovered)
                selector = SchemaRouterCatalogSelector(router)

                rows: list[dict[str, Any]] = []
                required_total = 0
                required_hits = 0
                unsupported_total = 0
                unsupported_rejections = 0
                input_schema_matches = 0
                output_schema_matches = 0
                output_schema_total = 0

                discovered_by_name = {tool.name: tool for tool in discovered}

                for query_case in CASES:
                    query = str(query_case["query"])
                    required = tuple(query_case["required_tools"])
                    allowed_bare = selector.select(query)
                    filtered_result = await agent.list_tools(
                        tool_filter={SERVER_NAME: allowed_bare}
                    )
                    filtered = list(filtered_result.tools)
                    filtered_names = {tool.name for tool in filtered}
                    expected_namespaced = {
                        bare_to_namespaced[name]
                        for name in allowed_bare
                        if name in bare_to_namespaced
                    }
                    assert filtered_names == expected_namespaced

                    if required:
                        required_total += len(required)
                        required_hits += sum(
                            bare_to_namespaced[name] in filtered_names
                            for name in required
                        )
                        success = all(
                            bare_to_namespaced[name] in filtered_names
                            for name in required
                        )
                    else:
                        unsupported_total += 1
                        success = not filtered
                        unsupported_rejections += int(success)

                    for filtered_tool in filtered:
                        source = discovered_by_name[filtered_tool.name]
                        input_schema_matches += int(
                            _input_schema(filtered_tool) == _input_schema(source)
                        )
                        source_output = _output_schema(source)
                        if source_output:
                            output_schema_total += 1
                            output_schema_matches += int(
                                _output_schema(filtered_tool) == source_output
                            )

                    rows.append(
                        {
                            "query": query,
                            "required_tools": list(required),
                            "sensitive": bool(query_case.get("sensitive", False)),
                            "selected_bare_tools": sorted(allowed_bare),
                            "exposed_namespaced_tools": sorted(filtered_names),
                            "shortlist_size": len(filtered),
                            "retrieval_task_success": success,
                            "revealed_schema_bytes": _serialized_tool_bytes(filtered),
                            "routing_latency_ms": selector.evidence[query][
                                "routing_latency_ms"
                            ],
                            "retrieval_evidence": selector.evidence[query],
                        }
                    )

                tool_calls = (
                    call_log.read_text(encoding="utf-8").splitlines()
                    if call_log.exists()
                    else []
                )

                lifecycle_manager_name = type(
                    app.server_registry.connection_manager
                ).__name__

    mirror_input_matches = 0
    mirror_output_matches = 0
    mirror_output_total = 0
    conversion_friction: list[dict[str, Any]] = []
    for source in discovered:
        bare = _bare_name(source.name)
        endpoint = router.registry.get(bare).endpoint("invoke")
        mirror_input_matches += int(endpoint.input_schema == _input_schema(source))
        source_output = _output_schema(source)
        if source_output:
            mirror_output_total += 1
            mirror_output_matches += int(endpoint.output_schema == source_output)
        omissions = _typed_promotion_omissions(source)
        if omissions:
            conversion_friction.append(
                {
                    "tool": source.name,
                    "raw_metadata_retained": True,
                    "not_promoted_to_typed_fields": omissions,
                }
            )

    required_recall = (
        required_hits / required_total if required_total else 1.0
    )
    unsupported_rejection = (
        unsupported_rejections / unsupported_total
        if unsupported_total
        else 1.0
    )
    task_success = (
        sum(int(row["retrieval_task_success"]) for row in rows) / len(rows)
    )
    latencies = [float(row["routing_latency_ms"]) for row in rows]

    result = {
        "schema_version": 1,
        "integration": "mcp-agent-catalog-retrieval",
        "mcp_agent_version": version("mcp-agent"),
        "schemarouter_version": version("schemarouter"),
        "boundary": {
            "lifecycle_owner": "mcp-agent",
            "mcp_agent_path": (
                "MCPApp -> Agent(connection_persistence=True) -> "
                "Agent.list_tools(tool_filter=...)"
            ),
            "schemarouter_role": "retrieval-only catalog mirror and bare-name allow-set",
            "execution_through_schemarouter": False,
            "llm_attached": False,
            "connection_manager_class": lifecycle_manager_name,
        },
        "catalog": {
            "discovered_tool_count": len(discovered),
            "full_serialized_schema_bytes": _serialized_tool_bytes(discovered),
            "max_results": selector.max_results,
        },
        "summary": {
            "required_tool_recall": required_recall,
            "unsupported_rejection": unsupported_rejection,
            "retrieval_task_success_rate": task_success,
            "mean_shortlist_size": round(
                statistics.mean(row["shortlist_size"] for row in rows),
                6,
            ),
            "mean_routing_latency_ms": round(statistics.mean(latencies), 6),
            "max_routing_latency_ms": round(max(latencies), 6),
            "input_schema_exact_matches": mirror_input_matches,
            "input_schema_total": len(discovered),
            "output_schema_exact_matches": mirror_output_matches,
            "output_schema_total": mirror_output_total,
            "mcp_agent_filtered_input_schema_exact_matches": input_schema_matches,
            "mcp_agent_filtered_output_schema_exact_matches": output_schema_matches,
            "mcp_agent_filtered_output_schema_total": output_schema_total,
            "mcp_tool_calls_during_evaluation": len(tool_calls),
            "tools_with_typed_promotion_friction": len(conversion_friction),
        },
        "conversion_friction": conversion_friction,
        "known_fidelity_limits": [
            (
                "SchemaRouter mirrors MCP name, description, input JSON Schema, "
                "output JSON Schema when declared, and read/destructive hints when "
                "they are explicit booleans."
            ),
            (
                "MCP metadata that has no dedicated SchemaRouter typed field is retained "
                "as raw source metadata and listed in conversion_friction rather than "
                "being silently reinterpreted."
            ),
            (
                "No field-level semantic IDs, units, authority, or execution binding "
                "are fabricated from MCP schemas when the source does not declare them."
            ),
            (
                "mcp-agent remains authoritative for server registry, connection manager, "
                "agent lifecycle, namespacing, filtering, and eventual tool invocation."
            ),
            (
                "Serialized schema bytes are context-size evidence, not model-token counts."
            ),
            (
                "retrieval_task_success_rate measures shortlist correctness only, "
                "not final model-answer quality."
            ),
        ],
        "cases": rows,
    }

    assert lifecycle_manager_name == "MCPConnectionManager", result
    assert required_recall == 1.0, result
    assert unsupported_rejection == 1.0, result
    assert task_success == 1.0, result
    assert mirror_input_matches == len(discovered), result
    assert not tool_calls, result

    return result


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = await evaluate()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())

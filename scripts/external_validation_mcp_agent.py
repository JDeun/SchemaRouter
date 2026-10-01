"""mcp-agent large-tool-catalog composition evaluation.

mcp-agent owns the MCP application, connection/session lifecycle, tool filtering,
and tool invocation. SchemaRouter receives a retrieval-only mirror of discovered
tool schemas and returns a bounded allow-set.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import statistics
import sys
import tempfile
import time
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp
from mcp_agent.config import (
    LoggerSettings,
    MCPServerSettings,
    MCPSettings,
    OpenTelemetrySettings,
    Settings,
    UsageTelemetrySettings,
)

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec

SERVER_NAME = "catalog"
SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "external_validation"
    / "mcp_agent_catalog"
    / "server.py"
)
_IDENTIFIER_TOKEN_RE = re.compile(r"[a-z0-9]+")

CASES: tuple[dict[str, Any], ...] = (
    {
        "query": "current weather in Seoul",
        "required_tools": ("weather_lookup",),
        "calls": (("weather_lookup", {"city": "Seoul"}),),
    },
    {
        "query": "find a hotel and restaurant in Seoul",
        "required_tools": ("hotel_search", "restaurant_search"),
        "calls": (
            ("hotel_search", {"city": "Seoul"}),
            ("restaurant_search", {"city": "Seoul"}),
        ),
    },
    {
        "query": "material band gap for silicon",
        "required_tools": ("material_band_gap",),
        "calls": (("material_band_gap", {"formula": "Si"}),),
    },
    {
        "query": "research paper about retrieval augmented generation",
        "required_tools": ("paper_search",),
        "calls": (("paper_search", {"query": "retrieval augmented generation"}),),
    },
    {
        "query": "compose a string quartet with counterpoint and harmony",
        "required_tools": (),
        "calls": (),
    },
)


def _assert_installed_wheel() -> None:
    package_file = Path(inspect.getfile(SchemaRouter)).resolve()
    repository_root = Path(__file__).resolve().parents[1]
    assert repository_root not in package_file.parents, package_file
    assert "site-packages" in package_file.parts, package_file


def _raw_name(namespaced_name: str) -> str:
    prefix = f"{SERVER_NAME}_"
    if not namespaced_name.startswith(prefix):
        raise AssertionError(
            f"mcp-agent returned unexpected tool namespace: {namespaced_name!r}"
        )
    return namespaced_name[len(prefix) :]


def _input_schema(tool: Any) -> dict[str, Any]:
    for attribute in ("inputSchema", "input_schema"):
        value = getattr(tool, attribute, None)
        if isinstance(value, dict):
            return deepcopy(value)
    return {}


def _output_schema(tool: Any) -> dict[str, Any]:
    for attribute in ("outputSchema", "output_schema"):
        value = getattr(tool, attribute, None)
        if isinstance(value, dict):
            return deepcopy(value)
    return {}


def _annotations(tool: Any) -> dict[str, Any]:
    value = getattr(tool, "annotations", None)
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json", by_alias=True, exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _source_dump(tool: Any) -> dict[str, Any]:
    dumped = tool.model_dump(mode="json", by_alias=True, exclude_none=True)
    return dumped if isinstance(dumped, dict) else {}


def _annotation_bool(annotations: dict[str, Any], *names: str) -> bool | None:
    for name in names:
        value = annotations.get(name)
        if isinstance(value, bool):
            return value
    return None


def _serialized_tool_bytes(tools: list[Any]) -> int:
    payload = [_source_dump(tool) for tool in tools]
    return len(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _register_retrieval_mirror(
    router: SchemaRouter,
    discovered: list[Any],
) -> dict[str, dict[str, Any]]:
    conversion: dict[str, dict[str, Any]] = {}

    for tool in discovered:
        raw_name = _raw_name(tool.name)
        input_schema = _input_schema(tool)
        output_schema = _output_schema(tool)
        annotations = _annotations(tool)
        source = _source_dump(tool)

        standard_keys = {
            "name",
            "description",
            "inputSchema",
            "input_schema",
            "outputSchema",
            "output_schema",
            "annotations",
        }
        opaque_source = {
            key: deepcopy(value)
            for key, value in source.items()
            if key not in standard_keys
        }

        read_only = _annotation_bool(
            annotations,
            "readOnlyHint",
            "read_only_hint",
        )
        destructive = _annotation_bool(
            annotations,
            "destructiveHint",
            "destructive_hint",
        )

        endpoint = EndpointSpec(
            name="invoke",
            description=tool.description or "",
            input_schema=input_schema,
            output_schema=output_schema,
            read_only=read_only,
            destructive=destructive,
            metadata={
                "mcp_annotations": deepcopy(annotations),
                "mcp_source_metadata": opaque_source,
            },
        )
        router.add_tool(
            ToolSpec(
                name=raw_name,
                description=tool.description or "",
                provider="mcp-agent",
                access_mode="mcp-agent-retrieval-mirror",
                source_type="mcp",
                endpoints=[endpoint],
            )
        )

        conversion[raw_name] = {
            "input_schema": input_schema,
            "output_schema": output_schema,
            "annotations": annotations,
            "opaque_source_metadata": opaque_source,
            "typed_read_only": read_only,
            "typed_destructive": destructive,
        }

    return conversion


class SchemaRouterCatalogSelector:
    """Conservative retrieval gate for mcp-agent's native tool filter."""

    def __init__(self, router: SchemaRouter, *, max_results: int = 4) -> None:
        self.router = router
        self.max_results = max_results

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return set(_IDENTIFIER_TOKEN_RE.findall(value.casefold()))

    def select(self, query: str) -> tuple[list[str], list[dict[str, Any]], float]:
        started = time.perf_counter()
        retrieval = self.router.retrieve(query, k=self.max_results)
        query_tokens = self._tokens(query)

        selected: list[str] = []
        evidence: list[dict[str, Any]] = []
        for candidate in retrieval.candidates:
            identifier_overlap = sorted(
                query_tokens.intersection(self._tokens(candidate.tool))
            )
            reveal = bool(identifier_overlap)
            evidence.append(
                {
                    "tool": candidate.tool,
                    "score": candidate.score,
                    "identifier_overlap": identifier_overlap,
                    "revealed": reveal,
                    "score_components": [
                        component.model_dump(mode="json")
                        for component in candidate.score_components
                    ],
                }
            )
            if reveal and candidate.tool not in selected:
                selected.append(candidate.tool)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return selected[: self.max_results], evidence, elapsed_ms


def _settings(call_log: Path) -> Settings:
    return Settings(
        name="schemarouter-mcp-agent-validation",
        execution_engine="asyncio",
        mcp=MCPSettings(
            servers={
                SERVER_NAME: MCPServerSettings(
                    name=SERVER_NAME,
                    transport="stdio",
                    command=sys.executable,
                    args=[str(SERVER_PATH)],
                    cwd=str(SERVER_PATH.parents[3]),
                    env={"SCHEMAROUTER_MCP_AGENT_CALL_LOG": str(call_log)},
                )
            }
        ),
        logger=LoggerSettings(
            type="none",
            transports=["none"],
            progress_display=False,
        ),
        otel=OpenTelemetrySettings(enabled=False),
        usage_telemetry=UsageTelemetrySettings(enabled=False),
    )


async def evaluate() -> dict[str, Any]:
    _assert_installed_wheel()

    with tempfile.TemporaryDirectory(prefix="schemarouter-mcp-agent-") as tmp:
        call_log = Path(tmp) / "tool-calls.jsonl"
        app = MCPApp(
            name="schemarouter-mcp-agent-validation",
            settings=_settings(call_log),
        )

        async with app.run() as running_app:
            agent = Agent(
                name="catalog-validation-agent",
                instruction="Deterministic validation; no LLM is attached.",
                server_names=[SERVER_NAME],
                context=running_app.context,
            )

            async with agent:
                discovered_result = await agent.list_tools()
                discovered = list(discovered_result.tools)
                assert len(discovered) >= 10

                router = SchemaRouter()
                conversion = _register_retrieval_mirror(router, discovered)
                selector = SchemaRouterCatalogSelector(router)

                rows: list[dict[str, Any]] = []
                required_total = 0
                required_hits = 0
                unsupported_total = 0
                unsupported_rejections = 0
                completed_tasks = 0
                routing_latencies: list[float] = []

                by_raw_name = {
                    _raw_name(tool.name): tool
                    for tool in discovered
                }

                for case in CASES:
                    query = str(case["query"])
                    required = tuple(case["required_tools"])
                    selected, evidence, latency_ms = selector.select(query)
                    routing_latencies.append(latency_ms)

                    filtered_result = await agent.list_tools(
                        tool_filter={SERVER_NAME: set(selected)}
                    )
                    filtered_tools = list(filtered_result.tools)
                    filtered_raw_names = [
                        _raw_name(tool.name)
                        for tool in filtered_tools
                    ]

                    assert set(filtered_raw_names) == set(selected)

                    call_results: list[dict[str, Any]] = []
                    calls_ok = True
                    for raw_tool_name, arguments in case["calls"]:
                        namespaced_name = by_raw_name[raw_tool_name].name
                        result = await agent.call_tool(
                            namespaced_name,
                            arguments=dict(arguments),
                        )
                        is_error = bool(getattr(result, "isError", False))
                        calls_ok = calls_ok and not is_error
                        call_results.append(
                            {
                                "tool": raw_tool_name,
                                "namespaced_tool": namespaced_name,
                                "is_error": is_error,
                            }
                        )

                    if required:
                        required_total += len(required)
                        hits = sum(
                            name in filtered_raw_names
                            for name in required
                        )
                        required_hits += hits
                        shortlist_ok = hits == len(required)
                        task_complete = shortlist_ok and calls_ok
                    else:
                        unsupported_total += 1
                        shortlist_ok = not filtered_raw_names
                        unsupported_rejections += int(shortlist_ok)
                        task_complete = shortlist_ok

                    completed_tasks += int(task_complete)
                    rows.append(
                        {
                            "query": query,
                            "required_tools": list(required),
                            "selected_tools": filtered_raw_names,
                            "shortlist_size": len(filtered_raw_names),
                            "retrieval_task_success": shortlist_ok,
                            "task_complete": task_complete,
                            "calls": call_results,
                            "routing_latency_ms": round(latency_ms, 6),
                            "revealed_schema_bytes": _serialized_tool_bytes(
                                filtered_tools
                            ),
                            "retrieval_evidence": evidence,
                        }
                    )

        call_records = (
            [
                json.loads(line)
                for line in call_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if call_log.exists()
            else []
        )

    input_matches = 0
    output_present = 0
    output_matches = 0
    annotation_present = 0
    opaque_top_level_fields: set[str] = set()
    annotation_metadata_only_fields: set[str] = set()

    for tool in discovered:
        raw_name = _raw_name(tool.name)
        mirror = router.registry.get(raw_name).endpoint("invoke")
        source_conversion = conversion[raw_name]

        input_matches += int(
            mirror.input_schema == source_conversion["input_schema"]
        )
        if source_conversion["output_schema"]:
            output_present += 1
            output_matches += int(
                mirror.output_schema == source_conversion["output_schema"]
            )
        if source_conversion["annotations"]:
            annotation_present += 1
            annotation_metadata_only_fields.update(
                source_conversion["annotations"].keys()
            )
            annotation_metadata_only_fields.difference_update(
                {
                    "readOnlyHint",
                    "read_only_hint",
                    "destructiveHint",
                    "destructive_hint",
                }
            )
        opaque_top_level_fields.update(
            source_conversion["opaque_source_metadata"].keys()
        )

    required_tool_recall = (
        required_hits / required_total
        if required_total
        else 1.0
    )
    unsupported_rejection = (
        unsupported_rejections / unsupported_total
        if unsupported_total
        else 1.0
    )
    task_completion_rate = completed_tasks / len(CASES)

    result = {
        "schema_version": 1,
        "integration": "mcp-agent-large-tool-catalog",
        "mcp_agent_version": version("mcp-agent"),
        "schemarouter_version": version("schemarouter"),
        "boundary": {
            "schemarouter_role": (
                "retrieval-only mirror and bounded allow-set generation"
            ),
            "mcp_agent_role": (
                "MCPApp lifecycle, stdio connection/session ownership, "
                "tool filtering, workflow orchestration, and tool invocation"
            ),
            "mcp_agent_owns_lifecycle": True,
            "execution_through_schemarouter": False,
            "hosted_model_used": False,
        },
        "catalog": {
            "discovered_tool_count": len(discovered),
            "full_serialized_schema_bytes": _serialized_tool_bytes(discovered),
            "max_results": selector.max_results,
        },
        "summary": {
            "required_tool_recall": required_tool_recall,
            "unsupported_rejection": unsupported_rejection,
            "task_completion_rate": task_completion_rate,
            "mean_shortlist_size": round(
                statistics.mean(row["shortlist_size"] for row in rows),
                6,
            ),
            "mean_routing_latency_ms": round(
                statistics.mean(routing_latencies),
                6,
            ),
            "max_routing_latency_ms": round(max(routing_latencies), 6),
            "mcp_tool_calls_via_mcp_agent": len(call_records),
        },
        "schema_conversion": {
            "input_schema_exact_matches": input_matches,
            "input_schema_total": len(discovered),
            "output_schema_present": output_present,
            "output_schema_exact_matches": output_matches,
            "annotations_present": annotation_present,
            "typed_conversion_gaps": {
                "top_level_fields_preserved_only_as_metadata": sorted(
                    opaque_top_level_fields
                ),
                "annotation_fields_preserved_only_as_metadata": sorted(
                    annotation_metadata_only_fields
                ),
                "output_fields_inferred": False,
            },
            "raw_metadata_preserved": True,
            "execution_binding_attached": False,
            "authority_metadata_fabricated": False,
        },
        "known_fidelity_limits": [
            (
                "SchemaRouter does not reconstruct mcp-agent connection/session "
                "state or invocation authority. Its mirror is intentionally "
                "non-executable."
            ),
            (
                "MCP input and declared output JSON Schemas are copied exactly "
                "when present. No output FieldSpec objects are inferred from "
                "schemas that do not declare SchemaRouter semantic metadata."
            ),
            (
                "MCP annotation fields without a direct typed EndpointSpec "
                "equivalent are preserved as source metadata and reported as "
                "typed conversion gaps rather than silently dropped."
            ),
            (
                "Serialized schema bytes are context-size evidence, not "
                "model-token counts."
            ),
            (
                "task_completion_rate measures this deterministic filtered "
                "workflow and direct mcp-agent tool calls, not LLM answer quality."
            ),
        ],
        "mcp_tool_call_log": call_records,
        "cases": rows,
    }

    expected_calls = sum(len(case["calls"]) for case in CASES)
    assert required_tool_recall == 1.0, result
    assert unsupported_rejection == 1.0, result
    assert task_completion_rate == 1.0, result
    assert input_matches == len(discovered), result
    assert len(call_records) == expected_calls, result

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

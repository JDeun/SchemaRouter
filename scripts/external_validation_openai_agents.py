"""OpenAI Agents SDK dynamic MCP filter composition evaluation.

SchemaRouter supplies a bounded allow-set only. The OpenAI Agents SDK retains
the MCP lifecycle, tool conversion, approval policy, guardrails, and invocation.
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
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agents import Agent, RunContextWrapper, ToolGuardrailFunctionOutput
from agents.decorators import tool_input_guardrail, tool_output_guardrail
from agents.mcp import MCPServerStdio, ToolFilterContext
from mcp.types import Tool as MCPTool

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec

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


@dataclass(frozen=True)
class SearchContext:
    query: str


@tool_input_guardrail
def validation_input_guardrail(_data: Any) -> ToolGuardrailFunctionOutput:
    return ToolGuardrailFunctionOutput.allow(output_info="validation-input-guardrail")


@tool_output_guardrail
def validation_output_guardrail(_data: Any) -> ToolGuardrailFunctionOutput:
    return ToolGuardrailFunctionOutput.allow(output_info="validation-output-guardrail")


def _input_schema(tool: MCPTool) -> dict[str, Any]:
    for attribute in ("inputSchema", "input_schema"):
        value = getattr(tool, attribute, None)
        if isinstance(value, dict):
            return deepcopy(value)
    return {"type": "object", "properties": {}}


def _description(tool: MCPTool) -> str:
    value = getattr(tool, "description", None)
    return value if isinstance(value, str) else ""


def _serialized_mcp_tool_bytes(tools: list[MCPTool]) -> int:
    payload = [
        {
            "name": tool.name,
            "description": _description(tool),
            "input_schema": _input_schema(tool),
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


def _serialized_function_tool_bytes(tools: list[Any]) -> int:
    payload = [
        {
            "name": tool.name,
            "description": tool.description,
            "params_json_schema": tool.params_json_schema,
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


def _assert_installed_wheel() -> None:
    package_file = Path(inspect.getfile(SchemaRouter)).resolve()
    repository_root = Path(__file__).resolve().parents[1]
    assert repository_root not in package_file.parents, package_file
    assert "site-packages" in package_file.parts, package_file


def _register_mcp_retrieval_mirror(
    router: SchemaRouter,
    tools: list[MCPTool],
) -> None:
    for tool in tools:
        is_destructive = tool.name == "delete_record"
        router.add_tool(
            ToolSpec(
                name=tool.name,
                description=_description(tool),
                provider="openai-agents-local-mcp",
                access_mode="mcp-stdio-filter-mirror",
                source_type="mcp",
                remote=True,
                endpoints=[
                    EndpointSpec(
                        name="invoke",
                        description=_description(tool),
                        input_schema=_input_schema(tool),
                        read_only=not is_destructive,
                        destructive=is_destructive,
                    )
                ],
            )
        )


class SchemaRouterDynamicMCPFilter:
    """Query-dependent Agents SDK tool filter backed by SchemaRouter retrieval."""

    def __init__(self, router: SchemaRouter, *, max_results: int = 4) -> None:
        self.router = router
        self.max_results = max_results
        self._cache: dict[str, set[str]] = {}
        self.evidence: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _identifier_tokens(value: str) -> set[str]:
        return set(_IDENTIFIER_TOKEN_RE.findall(value.casefold()))

    @classmethod
    def _has_disclosure_signal(cls, candidate: Any) -> bool:
        identifier_tokens = cls._identifier_tokens(candidate.tool)
        for component in candidate.score_components:
            matched = component.matched
            if (
                component.kind == "tool_token"
                and isinstance(matched, str)
                and matched.casefold() in identifier_tokens
            ):
                return True
            if component.kind in {"preferred_tool", "preferred_endpoint"}:
                return True
        return False

    def allow_set(self, query: str) -> set[str]:
        if query in self._cache:
            return self._cache[query]

        started = time.perf_counter()
        retrieval = self.router.retrieve(query, k=self.max_results)
        selected = [
            candidate.tool
            for candidate in retrieval.candidates
            if self._has_disclosure_signal(candidate)
        ]
        selected = list(dict.fromkeys(selected))[: self.max_results]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        allowed = set(selected)
        self._cache[query] = allowed
        self.evidence[query] = {
            "selected_tools": selected,
            "routing_latency_ms": round(elapsed_ms, 6),
            "candidates": [
                {
                    "tool": candidate.tool,
                    "score": candidate.score,
                    "score_components": [
                        component.model_dump(mode="json")
                        for component in candidate.score_components
                    ],
                    "disclosure_signal": self._has_disclosure_signal(candidate),
                }
                for candidate in retrieval.candidates
            ],
        }
        return allowed

    def __call__(self, context: ToolFilterContext, tool: MCPTool) -> bool:
        search_context = context.run_context.context
        if not isinstance(search_context, SearchContext):
            return False
        return tool.name in self.allow_set(search_context.query)


def _server_params(call_log: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["SCHEMAROUTER_OPENAI_AGENTS_CALL_LOG"] = str(call_log)
    return {
        "command": sys.executable,
        "args": [str(SERVER_PATH)],
        "cwd": str(SERVER_PATH.parents[3]),
        "env": env,
    }


async def evaluate() -> dict[str, Any]:
    _assert_installed_wheel()

    with tempfile.TemporaryDirectory(prefix="schemarouter-openai-agents-") as tmp:
        call_log = Path(tmp) / "tool-calls.jsonl"

        async with MCPServerStdio(
            params=_server_params(call_log),
            name="SchemaRouter validation discovery",
        ) as discovery_server:
            discovered = await discovery_server.list_tools()

        assert len(discovered) >= 10
        discovered_by_name = {tool.name: tool for tool in discovered}

        router = SchemaRouter()
        _register_mcp_retrieval_mirror(router, discovered)
        dynamic_filter = SchemaRouterDynamicMCPFilter(router)

        async with MCPServerStdio(
            params=_server_params(call_log),
            name="SchemaRouter validation filtered",
            tool_filter=dynamic_filter,
            require_approval="always",
            tool_input_guardrails=[validation_input_guardrail],
            tool_output_guardrails=[validation_output_guardrail],
        ) as filtered_server:
            agent = Agent[SearchContext](
                name="SchemaRouter Filter Validation",
                instructions="Validation-only agent; no model run is performed.",
                mcp_servers=[filtered_server],
            )

            rows: list[dict[str, Any]] = []
            total_required = 0
            required_hits = 0
            unsupported_total = 0
            unsupported_rejections = 0
            approval_preserved = True
            input_guardrail_preserved = True
            output_guardrail_preserved = True
            agents_schema_matches = 0
            agents_schema_total = 0

            for case in CASES:
                query = str(case["query"])
                required = tuple(case["required_tools"])
                run_context = RunContextWrapper(context=SearchContext(query=query))
                function_tools = await agent.get_mcp_tools(run_context)
                names = [tool.name for tool in function_tools]
                allow_set = dynamic_filter.allow_set(query)

                assert set(names) == allow_set

                if required:
                    total_required += len(required)
                    required_hits += sum(name in names for name in required)
                    success = all(name in names for name in required)
                else:
                    unsupported_total += 1
                    success = not names
                    unsupported_rejections += int(success)

                for tool in function_tools:
                    approval_preserved = (
                        approval_preserved and tool.needs_approval is True
                    )
                    input_guardrail_preserved = (
                        input_guardrail_preserved
                        and tool.tool_input_guardrails == [validation_input_guardrail]
                    )
                    output_guardrail_preserved = (
                        output_guardrail_preserved
                        and tool.tool_output_guardrails == [validation_output_guardrail]
                    )
                    raw = discovered_by_name[tool.name]
                    agents_schema_total += 1
                    if tool.params_json_schema == _input_schema(raw):
                        agents_schema_matches += 1

                rows.append(
                    {
                        "query": query,
                        "required_tools": list(required),
                        "sensitive": bool(case.get("sensitive", False)),
                        "selected_tools": names,
                        "shortlist_size": len(names),
                        "retrieval_task_success": success,
                        "revealed_schema_bytes": _serialized_function_tool_bytes(
                            function_tools
                        ),
                        "routing_latency_ms": dynamic_filter.evidence[query][
                            "routing_latency_ms"
                        ],
                        "filter_evidence": dynamic_filter.evidence[query],
                        "approval_preserved": all(
                            tool.needs_approval is True for tool in function_tools
                        ),
                        "input_guardrail_preserved": all(
                            tool.tool_input_guardrails == [validation_input_guardrail]
                            for tool in function_tools
                        ),
                        "output_guardrail_preserved": all(
                            tool.tool_output_guardrails == [validation_output_guardrail]
                            for tool in function_tools
                        ),
                    }
                )

        tool_calls = (
            call_log.read_text(encoding="utf-8").splitlines()
            if call_log.exists()
            else []
        )

    mirror_schema_matches = 0
    for raw in discovered:
        endpoint = router.registry.get(raw.name).endpoint("invoke")
        if endpoint.input_schema == _input_schema(raw):
            mirror_schema_matches += 1

    latencies = [
        float(row["routing_latency_ms"])
        for row in rows
    ]
    required_tool_recall = required_hits / total_required if total_required else 1.0
    unsupported_rejection = (
        unsupported_rejections / unsupported_total
        if unsupported_total
        else 1.0
    )
    retrieval_success = (
        sum(int(row["retrieval_task_success"]) for row in rows) / len(rows)
    )

    result = {
        "schema_version": 1,
        "integration": "openai-agents-dynamic-mcp-filter",
        "openai_agents_version": version("openai-agents"),
        "schemarouter_version": version("schemarouter"),
        "boundary": {
            "schemarouter_role": "retrieval-only query-dependent MCP allow-set",
            "agents_sdk_role": (
                "MCP process/session lifecycle, tool conversion, approvals, "
                "guardrails, and invocation"
            ),
            "execution_through_schemarouter": False,
            "hosted_model_used": False,
        },
        "catalog": {
            "discovered_tool_count": len(discovered),
            "full_serialized_schema_bytes": _serialized_mcp_tool_bytes(discovered),
            "max_results": dynamic_filter.max_results,
        },
        "summary": {
            "required_tool_recall": required_tool_recall,
            "unsupported_rejection": unsupported_rejection,
            "retrieval_task_success_rate": retrieval_success,
            "mean_shortlist_size": round(
                statistics.mean(row["shortlist_size"] for row in rows),
                6,
            ),
            "mean_routing_latency_ms": round(statistics.mean(latencies), 6),
            "max_routing_latency_ms": round(max(latencies), 6),
            "mirror_input_schema_exact_matches": mirror_schema_matches,
            "mirror_input_schema_total": len(discovered),
            "agents_filtered_schema_exact_matches": agents_schema_matches,
            "agents_filtered_schema_total": agents_schema_total,
            "approval_policy_preserved": approval_preserved,
            "input_guardrail_preserved": input_guardrail_preserved,
            "output_guardrail_preserved": output_guardrail_preserved,
            "mcp_tool_calls_during_evaluation": len(tool_calls),
        },
        "known_fidelity_limits": [
            (
                "SchemaRouter mirrors MCP name, description, and input JSON Schema "
                "for retrieval only; the Agents SDK remains authoritative for "
                "transport, invocation, approvals, and guardrails."
            ),
            (
                "The dynamic filter controls model-visible tool availability only. "
                "It is not an authorization mechanism for tool arguments or resources."
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

    assert required_tool_recall == 1.0, result
    assert unsupported_rejection == 1.0, result
    assert retrieval_success == 1.0, result
    assert mirror_schema_matches == len(discovered), result
    assert approval_preserved, result
    assert input_guardrail_preserved, result
    assert output_guardrail_preserved, result
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

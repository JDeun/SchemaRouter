"""Deterministic PydanticAI ToolSearch composition evaluation.

This is a retrieval-layer compatibility check. PydanticAI remains authoritative
for tool disclosure, lifecycle, and execution; SchemaRouter only returns bounded
tool names from a retrieval-only mirror of the PydanticAI ToolDefinition surface.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import statistics
import time
from collections.abc import Sequence
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pydantic_ai import ToolDefinition
from pydantic_ai.capabilities import ToolSearch

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    SchemaRouter,
    ToolSpec,
)


CATALOG: tuple[dict[str, Any], ...] = (
    {
        "name": "weather_lookup",
        "description": "Get current weather temperature and conditions for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
        "fields": (
            ("temperature", "weather.temperature"),
            ("conditions", "weather.conditions"),
        ),
    },
    {
        "name": "stock_quote",
        "description": "Get the latest stock market price for a ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
            "additionalProperties": False,
        },
        "fields": (("price", "finance.stock_price"),),
    },
    {
        "name": "currency_convert",
        "description": "Convert money between ISO currency codes.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from_currency": {"type": "string"},
                "to_currency": {"type": "string"},
            },
            "required": ["amount", "from_currency", "to_currency"],
            "additionalProperties": False,
        },
        "fields": (("converted_amount", "finance.converted_amount"),),
    },
    {
        "name": "flight_status",
        "description": "Get airline flight departure, arrival, and delay status.",
        "parameters": {
            "type": "object",
            "properties": {"flight_number": {"type": "string"}},
            "required": ["flight_number"],
            "additionalProperties": False,
        },
        "fields": (("status", "travel.flight_status"),),
    },
    {
        "name": "hotel_search",
        "description": "Find hotels and lodging options in a destination city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
        "fields": (("hotels", "travel.hotels"),),
    },
    {
        "name": "restaurant_search",
        "description": "Find restaurants and dining options in a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
        "fields": (("restaurants", "travel.restaurants"),),
    },
    {
        "name": "package_track",
        "description": "Track a parcel or shipment by tracking identifier.",
        "parameters": {
            "type": "object",
            "properties": {"tracking_id": {"type": "string"}},
            "required": ["tracking_id"],
            "additionalProperties": False,
        },
        "fields": (("shipment_status", "logistics.shipment_status"),),
    },
    {
        "name": "calendar_lookup",
        "description": "List calendar events for a date.",
        "parameters": {
            "type": "object",
            "properties": {"date": {"type": "string"}},
            "required": ["date"],
            "additionalProperties": False,
        },
        "fields": (("events", "calendar.events"),),
    },
    {
        "name": "issue_search",
        "description": "Search software project issues and bug reports.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "fields": (("issues", "software.issues"),),
    },
    {
        "name": "paper_search",
        "description": "Search research papers and scientific abstracts.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "fields": (
            ("title", "paper.title"),
            ("abstract", "paper.abstract"),
        ),
    },
    {
        "name": "material_band_gap",
        "description": "Get the electronic band gap for a material or chemical formula.",
        "parameters": {
            "type": "object",
            "properties": {"formula": {"type": "string"}},
            "required": ["formula"],
            "additionalProperties": False,
        },
        "fields": (("band_gap", "materials.band_gap"),),
    },
    {
        "name": "material_elastic_modulus",
        "description": "Get elastic modulus mechanical-property data for a material.",
        "parameters": {
            "type": "object",
            "properties": {"material_id": {"type": "string"}},
            "required": ["material_id"],
            "additionalProperties": False,
        },
        "fields": (("elastic_modulus", "materials.elastic_modulus"),),
    },
)

CASES: tuple[tuple[str, str | None], ...] = (
    ("current weather temperature in Seoul", "weather_lookup"),
    ("track parcel shipment ZX-1", "package_track"),
    ("research paper abstract about retrieval augmented generation", "paper_search"),
    ("electronic band gap for a silicon material", "material_band_gap"),
    ("compose a string quartet with counterpoint and harmony", None),
)


def _tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name=entry["name"],
            description=entry["description"],
            parameters_json_schema=deepcopy(entry["parameters"]),
            defer_loading=True,
        )
        for entry in CATALOG
    ]


def _field_hints() -> dict[str, tuple[tuple[str, str], ...]]:
    return {
        str(entry["name"]): tuple(entry["fields"])
        for entry in CATALOG
    }


def _register_retrieval_mirror(
    router: SchemaRouter,
    tools: Sequence[ToolDefinition],
) -> None:
    hints = _field_hints()
    for tool in tools:
        schema = deepcopy(tool.parameters_json_schema)
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        parameters = [
            ParameterSpec(
                name=name,
                required=name in required,
                json_schema=deepcopy(value),
            )
            for name, value in properties.items()
            if isinstance(name, str) and isinstance(value, dict)
        ]
        output_fields = [
            FieldSpec(name=name, semantic_id=semantic_id)
            for name, semantic_id in hints.get(tool.name, ())
        ]
        router.add_tool(
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                provider="pydanticai",
                access_mode="tool-search-mirror",
                remote=False,
                endpoints=[
                    EndpointSpec(
                        name="invoke",
                        description=tool.description or "",
                        parameters=parameters,
                        input_schema=schema,
                        output_fields=output_fields,
                        read_only=True,
                        destructive=False,
                    )
                ],
            )
        )


class SchemaRouterToolSearchStrategy:
    """PydanticAI ToolSearch strategy backed by SchemaRouter retrieval only.

    SchemaRouter's raw lexical score is recall-oriented: a generic token in a
    description can make an otherwise unsupported route score above zero. The
    integration therefore applies an explicit disclosure gate. A candidate is
    revealable only when SchemaRouter matched an output field, the caller
    explicitly preferred it, or a matched tool token belongs to the registered
    tool identifier itself rather than only to free-form description text.
    """

    _IDENTIFIER_TOKEN_RE = re.compile(r"[a-z0-9]+")

    def __init__(self, router: SchemaRouter, *, max_results: int = 3) -> None:
        self.router = router
        self.max_results = max_results

    @classmethod
    def _identifier_tokens(cls, value: str) -> set[str]:
        return set(cls._IDENTIFIER_TOKEN_RE.findall(value.casefold()))

    @classmethod
    def _disclosure_signal(cls, candidate: Any) -> str | None:
        if candidate.matched_fields:
            return "matched_field"

        identifier_tokens = cls._identifier_tokens(candidate.tool)
        for component in candidate.score_components:
            if component.kind in {"preferred_tool", "preferred_endpoint"}:
                return component.kind
            if (
                component.kind == "tool_token"
                and component.matched.casefold() in identifier_tokens
            ):
                return "tool_identifier_token"
        return None

    def search_with_evidence(
        self,
        query: str,
        tools: Sequence[ToolDefinition],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if not query.strip():
            return [], []

        allowed = {tool.name for tool in tools}
        retrieval = self.router.retrieve(
            query,
            k=min(max(self.max_results, 1), max(len(tools), 1)),
        )

        selected: list[str] = []
        evidence: list[dict[str, Any]] = []
        for candidate in retrieval.candidates:
            signal = self._disclosure_signal(candidate)
            evidence.append(
                {
                    "tool": candidate.tool,
                    "score": candidate.score,
                    "matched_fields": list(candidate.matched_fields),
                    "signal": signal,
                    "score_components": [
                        component.model_dump(mode="json")
                        for component in candidate.score_components
                    ],
                }
            )
            if signal is None:
                continue
            if candidate.tool not in allowed or candidate.tool in selected:
                continue
            selected.append(candidate.tool)
            if len(selected) >= self.max_results:
                break
        return selected, evidence

    def __call__(
        self,
        ctx: Any,
        queries: Sequence[str],
        tools: Sequence[ToolDefinition],
    ) -> list[str]:
        del ctx
        query = " ".join(part.strip() for part in queries if part.strip()).strip()
        selected, _ = self.search_with_evidence(query, tools)
        return selected


def _serialized_tool_bytes(tools: Sequence[ToolDefinition]) -> int:
    payload = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters_json_schema": tool.parameters_json_schema,
            "defer_loading": bool(getattr(tool, "defer_loading", False)),
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


def evaluate() -> dict[str, Any]:
    _assert_installed_wheel()

    tools = _tool_definitions()
    router = SchemaRouter()
    _register_retrieval_mirror(router, tools)
    strategy = SchemaRouterToolSearchStrategy(router, max_results=3)

    # Construction through PydanticAI's public capability API proves the callable
    # is accepted as a ToolSearch strategy. PydanticAI still owns reveal/execution.
    ToolSearch(strategy=strategy)

    rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    supported_hits = 0
    supported_total = 0
    unsupported_total = 0
    unsupported_rejections = 0

    by_name = {tool.name: tool for tool in tools}
    for query, required_tool in CASES:
        started = time.perf_counter()
        selected, candidate_evidence = strategy.search_with_evidence(query, tools)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)

        if required_tool is None:
            unsupported_total += 1
            success = not selected
            unsupported_rejections += int(success)
        else:
            supported_total += 1
            success = required_tool in selected
            supported_hits += int(success)

        selected_defs = [by_name[name] for name in selected]
        rows.append(
            {
                "query": query,
                "required_tool": required_tool,
                "selected_tools": selected,
                "candidate_evidence": candidate_evidence,
                "retrieval_task_success": success,
                "revealed_schema_bytes": _serialized_tool_bytes(selected_defs),
                "routing_latency_ms": round(elapsed_ms, 6),
            }
        )

    exact_schema_matches = 0
    for definition in tools:
        mirror = router.registry.get(definition.name).endpoint("invoke")
        if mirror.input_schema == definition.parameters_json_schema:
            exact_schema_matches += 1

    required_tool_recall = (
        supported_hits / supported_total if supported_total else 1.0
    )
    unsupported_rejection = (
        unsupported_rejections / unsupported_total
        if unsupported_total
        else 1.0
    )
    retrieval_task_success = (
        sum(int(row["retrieval_task_success"]) for row in rows) / len(rows)
    )

    result = {
        "schema_version": 1,
        "integration": "pydanticai-tool-search",
        "pydantic_ai_version": version("pydantic-ai"),
        "schemarouter_version": version("schemarouter"),
        "boundary": {
            "schemarouter_role": "retrieval-only mirror and bounded name selection",
            "pydanticai_role": "tool disclosure, lifecycle, validation, and execution",
            "execution_through_schemarouter": False,
            "disclosure_gate": (
                "matched output field, explicit preference, or tool-identifier token match"
            ),
        },
        "catalog": {
            "deferred_tool_count": len(tools),
            "full_serialized_schema_bytes": _serialized_tool_bytes(tools),
            "max_results": strategy.max_results,
        },
        "summary": {
            "supported_cases": supported_total,
            "required_tool_recall": required_tool_recall,
            "unsupported_cases": unsupported_total,
            "unsupported_rejection": unsupported_rejection,
            "retrieval_task_success_rate": retrieval_task_success,
            "mean_routing_latency_ms": round(statistics.mean(latencies_ms), 6),
            "max_routing_latency_ms": round(max(latencies_ms), 6),
            "input_schema_exact_matches": exact_schema_matches,
            "input_schema_total": len(tools),
        },
        "known_fidelity_limits": [
            (
                "The retrieval mirror copies name, description, and input JSON Schema; "
                "PydanticAI-specific execution, approval, timeout, strictness, kind, "
                "toolset lifecycle, and defer/reveal state remain authoritative in PydanticAI."
            ),
            (
                "Output semantic field hints are trusted evaluation metadata declared "
                "locally for SchemaRouter retrieval; they are not inferred from PydanticAI."
            ),
            (
                "Raw SchemaRouter lexical scores are recall-oriented and are not used as an "
                "abstention threshold. This integration adds a conservative disclosure gate "
                "based on matched fields, explicit preferences, or tool-identifier tokens."
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
    assert retrieval_task_success == 1.0, result
    assert exact_schema_matches == len(tools), result
    assert all(
        len(row["selected_tools"]) <= strategy.max_results
        for row in rows
    ), result

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = evaluate()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

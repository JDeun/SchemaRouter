"""Realistic SchemaRouter break-even benchmark for issue #691.

The matrix varies catalog size and sibling ambiguity. It compares:
1. a simple name/description lexical baseline;
2. a schema-aware lexical baseline;
3. exhaustive SchemaRouter route scoring (candidate_index=False);
4. optimized SchemaRouter route retrieval (candidate_index=True).

This is a deterministic retrieval benchmark with strict typed field contracts,
not an end-to-end agent benchmark.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from schemarouter import (
    EndpointSpec,
    EvidenceRequirements,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanningError,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)

TOKEN_RE = re.compile(r"[a-z0-9_]+")
SIZES = (20, 50, 100, 250, 500)
AMBIGUITIES = ("low", "medium", "high")
OPERATIONS = (
    "get",
    "list",
    "search",
    "status",
    "history",
    "export",
    "inspect",
    "lookup",
    "summarize",
    "validate",
)
Ambiguity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Case:
    query: str
    request: PlanRequest
    required_tool: str | None
    required_field: str | None
    supported: bool


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.casefold()))


def _catalog_shape(index: int, ambiguity: Ambiguity) -> tuple[str, str, str, str]:
    if ambiguity == "low":
        family = f"domain_{index}"
        operation = f"fetch_{index}"
        field = f"metric_{index}"
        description = f"Dedicated {family} {operation} capability"
    elif ambiguity == "medium":
        group = index // 4
        operation = OPERATIONS[index % 4]
        family = f"resource_{group}"
        field = f"metric_{index}"
        description = f"{operation} {family} records and return {field}"
    else:
        group = index // 10
        operation = OPERATIONS[index % 10]
        family = f"resource_{group}"
        field = "measurement"
        description = f"Manage {family} records and metadata"
    return family, operation, field, description


def build_catalog(size: int, ambiguity: Ambiguity) -> list[ToolSpec]:
    tools: list[ToolSpec] = []
    for index in range(size):
        family, operation, field, description = _catalog_shape(index, ambiguity)
        tools.append(
            ToolSpec(
                name=f"{family}_{operation}",
                description=description,
                provider="synthetic-enterprise",
                access_mode="local",
                endpoints=[
                    EndpointSpec(
                        name="invoke",
                        description=description,
                        read_only=True,
                        destructive=False,
                        parameters=[
                            ParameterSpec(
                                name="record_id",
                                required=False,
                                json_schema={"type": "string"},
                            )
                        ],
                        output_fields=[
                            FieldSpec(
                                name=field,
                                semantic_id=f"{family}.{field}",
                                aliases=[field.replace("_", " ")],
                                json_schema={"type": "number"},
                                unit="arb",
                                qualifiers=(
                                    {"channel": f"channel_{index % 10}"}
                                    if ambiguity == "high"
                                    else {}
                                ),
                            )
                        ],
                    )
                ],
            )
        )
    return tools


def build_cases(size: int, ambiguity: Ambiguity) -> list[Case]:
    supported_indexes = sorted(
        {
            round(position * (size - 1) / 11)
            for position in range(12)
        }
    )
    cases: list[Case] = []
    for position, index in enumerate(supported_indexes):
        family, operation, field, _ = _catalog_shape(index, ambiguity)
        tool_name = f"{family}_{operation}"
        if position % 2 == 0:
            if ambiguity == "high":
                query = f"{tool_name} {family}"
            else:
                query = f"{family} {operation}"
            cases.append(
                Case(
                    query=query,
                    request=PlanRequest(query=query),
                    required_tool=tool_name,
                    required_field=None,
                    supported=True,
                )
            )
        else:
            if ambiguity == "low":
                query = f"{family} {field}"
            elif ambiguity == "medium":
                query = f"{family} {operation} {field}"
            else:
                query = f"{family} {field} channel_{index % 10}"
            semantic_id = f"{family}.{field}"
            cases.append(
                Case(
                    query=query,
                    request=PlanRequest(
                        query=query,
                        concepts=[field],
                        field_evidence={
                            semantic_id: EvidenceRequirements(units=True),
                        },
                    ),
                    required_tool=tool_name,
                    required_field=semantic_id,
                    supported=True,
                )
            )

    unsupported_groups = min(4, max(1, size // 10))
    for offset in range(unsupported_groups):
        index = min(size - 1, offset * max(1, size // unsupported_groups))
        family, _, _, _ = _catalog_shape(index, ambiguity)
        missing = f"unsupported_field_{offset}"
        missing_semantic = f"{family}.{missing}"
        query = f"{family} {missing}"
        cases.append(
            Case(
                query=query,
                request=PlanRequest(
                    query=query,
                    concepts=[missing],
                    field_evidence={
                        missing_semantic: EvidenceRequirements(units=True),
                    },
                ),
                required_tool=None,
                required_field=missing_semantic,
                supported=False,
            )
        )
    return cases


def build_router(tools: list[ToolSpec], *, candidate_index: bool) -> SchemaRouter:
    registry = InMemoryRegistry()
    registry.update_many(tools)
    router = SchemaRouter(registry=registry)
    router.planner.candidate_index = candidate_index
    return router


def _baseline_documents(tools: list[ToolSpec]) -> list[tuple[str, set[str]]]:
    docs: list[tuple[str, set[str]]] = []
    for tool in tools:
        endpoint = tool.endpoints[0]
        text = " ".join(
            [
                tool.name,
                tool.description,
                endpoint.name,
                endpoint.description,
            ]
        )
        docs.append((tool.key, _tokens(text)))
    return docs


def _schema_lexical_documents(
    tools: list[ToolSpec],
) -> list[tuple[str, set[str], set[str]]]:
    docs: list[tuple[str, set[str], set[str]]] = []
    for tool in tools:
        endpoint = tool.endpoints[0]
        general = _tokens(
            " ".join(
                [
                    tool.name,
                    tool.description,
                    endpoint.name,
                    endpoint.description,
                ]
            )
        )
        fields: set[str] = set()
        for field in endpoint.output_fields:
            fields.update(
                _tokens(
                    " ".join(
                        [
                            field.name,
                            field.semantic_id or "",
                            *field.aliases,
                            *field.qualifiers.keys(),
                            *field.qualifiers.values(),
                        ]
                    )
                )
            )
        docs.append((tool.key, general, fields))
    return docs


def baseline_select(
    query: str,
    documents: list[tuple[str, set[str]]],
    *,
    k: int = 3,
) -> list[str]:
    query_tokens = _tokens(query)
    ranked = [
        (len(query_tokens & tokens), tool_key)
        for tool_key, tokens in documents
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [tool_key for score, tool_key in ranked[:k] if score > 0]


def schema_lexical_select(
    case: Case,
    documents: list[tuple[str, set[str], set[str]]],
    *,
    k: int = 3,
) -> list[str]:
    query_tokens = _tokens(case.query)
    required_field_tokens = (
        _tokens(case.required_field)
        if case.required_field is not None
        else set()
    )
    ranked: list[tuple[int, int, str]] = []
    for tool_key, general_tokens, field_tokens in documents:
        field_score = len(required_field_tokens & field_tokens)
        if required_field_tokens and not required_field_tokens.issubset(field_tokens):
            continue
        general_score = len(query_tokens & general_tokens)
        if not required_field_tokens and general_score == 0:
            continue
        ranked.append((field_score, general_score, tool_key))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [tool_key for _, _, tool_key in ranked[:k]]


def schemarouter_select(
    router: SchemaRouter,
    case: Case,
    *,
    k: int = 3,
) -> list[str]:
    try:
        result = router.retrieve_routes(case.request, k=k)
    except PlanningError:
        return []
    candidates = [candidate for candidate in result.candidates if candidate.score > 0]
    if case.required_field is not None:
        candidates = [candidate for candidate in candidates if candidate.matched_fields]
    return [candidate.tool for candidate in candidates]


def _contract_bytes(tools: list[ToolSpec]) -> dict[str, int]:
    result: dict[str, int] = {}
    for tool in tools:
        endpoint = tool.endpoints[0]
        payload = {
            "parameters": [
                parameter.model_dump(mode="json")
                for parameter in endpoint.parameters
            ],
            "output_fields": [
                field.model_dump(mode="json")
                for field in endpoint.output_fields
            ],
            "read_only": endpoint.read_only,
            "destructive": endpoint.destructive,
        }
        result[tool.key] = len(
            json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    return result


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


def _quality(
    cases: list[Case],
    selections: list[list[str]],
    contract_bytes: dict[str, int],
) -> dict[str, float]:
    supported = [
        (case, selected)
        for case, selected in zip(cases, selections, strict=True)
        if case.supported
    ]
    unsupported = [
        (case, selected)
        for case, selected in zip(cases, selections, strict=True)
        if not case.supported
    ]
    recall = statistics.mean(
        1.0 if case.required_tool in selected else 0.0
        for case, selected in supported
    )
    rejection = statistics.mean(
        1.0 if not selected else 0.0
        for _, selected in unsupported
    )
    false_route = statistics.mean(
        1.0 if selected else 0.0
        for _, selected in unsupported
    )
    selected_counts = [len(selected) for _, selected in zip(cases, selections, strict=True)]
    byte_counts = [
        sum(contract_bytes.get(tool_key, 0) for tool_key in selected)
        for selected in selections
    ]
    return {
        "required_tool_recall": recall,
        "unsupported_rejection": rejection,
        "false_route_rate": false_route,
        "mean_selected_candidates": statistics.mean(selected_counts),
        "mean_selected_contract_bytes": statistics.mean(byte_counts),
    }


def _timing(
    call,
    cases: list[Case],
    *,
    iterations: int,
) -> dict[str, float]:
    samples: list[float] = []
    for case in cases:
        call(case)
    for case in cases:
        for _ in range(iterations):
            started = time.perf_counter_ns()
            call(case)
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "sample_count": float(len(samples)),
        "p50_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "mean_ms": statistics.mean(samples),
    }


def evaluate_condition(
    size: int,
    ambiguity: Ambiguity,
    *,
    iterations: int,
) -> dict[str, Any]:
    tools = build_catalog(size, ambiguity)
    cases = build_cases(size, ambiguity)
    documents = _baseline_documents(tools)
    schema_documents = _schema_lexical_documents(tools)
    contract_bytes = _contract_bytes(tools)
    full = build_router(tools, candidate_index=False)
    auto = build_router(tools, candidate_index=True)

    methods = {
        "lexical_baseline": lambda case: baseline_select(case.query, documents),
        "schema_lexical_baseline": (
            lambda case: schema_lexical_select(case, schema_documents)
        ),
        "schemarouter_full": lambda case: schemarouter_select(full, case),
        "schemarouter_auto": lambda case: schemarouter_select(auto, case),
    }
    result: dict[str, Any] = {
        "catalog_size": size,
        "ambiguity": ambiguity,
        "supported_cases": sum(case.supported for case in cases),
        "unsupported_cases": sum(not case.supported for case in cases),
        "methods": {},
    }
    selections_by_method: dict[str, list[list[str]]] = {}
    for name, call in methods.items():
        selections = [call(case) for case in cases]
        selections_by_method[name] = selections
        result["methods"][name] = {
            **_quality(cases, selections, contract_bytes),
            **_timing(call, cases, iterations=iterations),
        }

    full_selections = selections_by_method["schemarouter_full"]
    auto_selections = selections_by_method["schemarouter_auto"]
    result["auto_full_selection_mismatches"] = sum(
        full_selected != auto_selected
        for full_selected, auto_selected in zip(
            full_selections,
            auto_selections,
            strict=True,
        )
    )

    strongest_simple = result["methods"]["schema_lexical_baseline"]
    auto_metrics = result["methods"]["schemarouter_auto"]
    if (
        strongest_simple["required_tool_recall"]
        >= auto_metrics["required_tool_recall"]
        and strongest_simple["unsupported_rejection"]
        >= auto_metrics["unsupported_rejection"]
    ):
        region = "simple-routing-sufficient-on-this-fixture"
    elif auto_metrics["p95_ms"] <= 3.0:
        region = "typed-routing-benefit-with-low-overhead"
    else:
        region = "typed-routing-benefit-with-measurable-overhead"
    result["break_even_region"] = region
    return result


def evaluate(iterations: int = 20) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    matrix = [
        evaluate_condition(size, ambiguity, iterations=iterations)
        for size in SIZES
        for ambiguity in AMBIGUITIES
    ]
    return {
        "schema_version": 1,
        "benchmark": "realistic-catalog-break-even",
        "sizes": list(SIZES),
        "ambiguities": list(AMBIGUITIES),
        "iterations_per_case": iterations,
        "matrix": matrix,
        "claim_boundary": (
            "Synthetic deterministic retrieval benchmark. It measures catalog-size and "
            "sibling-ambiguity effects; it does not establish production adoption or "
            "end-to-end agent-answer quality."
        ),
    }


def _compact_summary(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in result["matrix"]:
        row: dict[str, Any] = {
            "catalog_size": condition["catalog_size"],
            "ambiguity": condition["ambiguity"],
            "region": condition["break_even_region"],
            "auto_full_selection_mismatches": condition[
                "auto_full_selection_mismatches"
            ],
        }
        for name, metrics in condition["methods"].items():
            row[name] = {
                "recall": metrics["required_tool_recall"],
                "reject": metrics["unsupported_rejection"],
                "false_route": metrics["false_route_rate"],
                "p50_ms": metrics["p50_ms"],
                "p95_ms": metrics["p95_ms"],
                "contract_bytes": metrics["mean_selected_contract_bytes"],
            }
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    result = evaluate(args.iterations)
    print(json.dumps(_compact_summary(result), indent=2, sort_keys=True))
    print("SCHEMAROUTER_BREAK_EVEN_RESULT_BEGIN")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("SCHEMAROUTER_BREAK_EVEN_RESULT_END")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()

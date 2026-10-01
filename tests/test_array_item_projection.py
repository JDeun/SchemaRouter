from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    PlanValidationError,
    SchemaRouter,
    SchemaValidationError,
    ServerProjectionSpec,
    ToolCall,
    ToolSpec,
)
from schemarouter.validation import field_value_schema, projected_output_schema


def _endpoint() -> EndpointSpec:
    return EndpointSpec(
        name="search",
        read_only=True,
        destructive=False,
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "score"],
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "score": {"type": "number"},
                        },
                    },
                }
            },
            "required": ["results"],
        },
        output_fields=[
            FieldSpec(
                name="results",
                json_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "score": {"type": "number"},
                        },
                    },
                },
            ),
            FieldSpec(
                name="results[].title",
                path=["results", "*", "title"],
                result_path=["results", "*", "title"],
                json_schema={"type": "string"},
                aliases=["title"],
            ),
            FieldSpec(
                name="results[].url",
                path=["results", "*", "url"],
                result_path=["results", "*", "url"],
                json_schema={"type": "string"},
                aliases=["url"],
            ),
            FieldSpec(
                name="results[].score",
                path=["results", "*", "score"],
                result_path=["results", "*", "score"],
                json_schema={"type": "number"},
                unit="meV",
                unit_normalization={
                    "dimension": "energy",
                    "canonical_unit": "eV",
                    "scale": 0.001,
                    "offset": 0.0,
                },
                aliases=["score"],
            ),
        ],
    )


def _tool() -> ToolSpec:
    return ToolSpec(
        name="search_fixture",
        endpoints=[_endpoint()],
    )


def _call(tool: ToolSpec, fields: list[str]) -> ToolCall:
    endpoint = tool.endpoint("search")
    return ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=fields,
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )


def _raw_payload() -> dict:
    return {
        "results": [
            {"title": "A", "url": "https://a.test", "score": 1000.0},
            {"title": "B", "score": 2000.0},
            {"title": "C", "url": "https://c.test", "score": 3000.0},
        ]
    }


@pytest.mark.asyncio
async def test_array_child_projection_preserves_record_alignment() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    async def invoke(endpoint: str, arguments: dict) -> dict:
        del endpoint, arguments
        return _raw_payload()

    router.executor.bind(key, invoke, expected_fingerprint=tool.fingerprint)
    call = _call(tool, ["results[].title", "results[].url"])
    plan = ExecutionPlan(
        query="titles and urls",
        registry_version=router.registry.version,
        calls=[call],
    )

    results = await router.execute(plan)

    assert results[0].data == {
        "results": [
            {"title": "A", "url": "https://a.test"},
            {"title": "B"},
            {"title": "C", "url": "https://c.test"},
        ]
    }


@pytest.mark.asyncio
async def test_array_child_unit_normalization_preserves_positions() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    async def invoke(endpoint: str, arguments: dict) -> dict:
        del endpoint, arguments
        return _raw_payload()

    router.executor.bind(key, invoke, expected_fingerprint=tool.fingerprint)
    call = _call(tool, ["results[].score"])
    plan = ExecutionPlan(
        query="normalized scores",
        registry_version=router.registry.version,
        calls=[call],
    )

    results = await router.execute(plan)

    assert results[0].data == {
        "results": [
            {"score": 1.0},
            {"score": 2.0},
            {"score": 3.0},
        ]
    }
    contract = results[0].field_contracts["results[].score"]
    assert contract.source_unit == "meV"
    assert contract.unit == "eV"
    assert contract.dimension == "energy"


@pytest.mark.asyncio
async def test_array_child_schema_validation_checks_each_present_record() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)

    async def invoke(endpoint: str, arguments: dict) -> dict:
        del endpoint, arguments
        payload = _raw_payload()
        payload["results"][1]["title"] = 42
        return payload

    router.executor.bind(key, invoke, expected_fingerprint=tool.fingerprint)
    call = _call(tool, ["results[].title"])
    plan = ExecutionPlan(
        query="titles",
        registry_version=router.registry.version,
        calls=[call],
    )

    with pytest.raises(SchemaValidationError):
        await router.execute(plan)


@pytest.mark.asyncio
async def test_array_parent_and_descendant_cannot_be_selected_together() -> None:
    router = SchemaRouter()
    tool = _tool()
    key = router.add_tool(tool)
    calls = 0

    async def invoke(endpoint: str, arguments: dict) -> dict:
        nonlocal calls
        del endpoint, arguments
        calls += 1
        return _raw_payload()

    router.executor.bind(key, invoke, expected_fingerprint=tool.fingerprint)
    call = _call(tool, ["results", "results[].title"])
    plan = ExecutionPlan(
        query="ambiguous projection",
        registry_version=router.registry.version,
        calls=[call],
    )

    with pytest.raises(
        PlanValidationError,
        match="array parent.*wildcard descendants",
    ):
        await router.execute(plan)

    assert calls == 0


def test_array_field_path_requires_matching_result_wildcards() -> None:
    with pytest.raises(ValueError, match="matching wildcard counts"):
        FieldSpec(
            name="results[].title",
            path=["results", "*", "title"],
            result_path=["results.title"],
            json_schema={"type": "string"},
        )


def test_array_field_schema_resolves_through_items() -> None:
    endpoint = _endpoint()

    assert field_value_schema(
        endpoint,
        "results[].title",
    ) == {"type": "string"}


def test_server_projected_schema_narrows_nested_array_items() -> None:
    endpoint = _endpoint().model_copy(
        update={
            "server_projection": ServerProjectionSpec(
                parameter="fields",
                field_map={
                    "results[].title": "title",
                },
            )
        }
    )

    schema = projected_output_schema(
        endpoint,
        ["results[].title"],
    )

    result_schema = schema["properties"]["results"]
    item_schema = result_schema["items"]
    assert set(item_schema["properties"]) == {"title"}
    assert item_schema["required"] == ["title"]

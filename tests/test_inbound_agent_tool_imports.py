from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from schemarouter import (
    ExecutionPlan,
    PlanRequest,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import PlanValidationError, SchemaValidationError
from schemarouter.integrations import tool_from_langchain, tool_from_llamaindex


class SearchArgs(BaseModel):
    query: str
    limit: int = 3


class SearchOutput(BaseModel):
    answer: str
    count: int


class SearchHit(BaseModel):
    title: str
    url: str
    score: float | None = None


class SearchBatch(BaseModel):
    results: list[SearchHit]


class FakeLangChainResultsTool:
    name = "web_results"
    description = "Search the web and return structured results."
    args_schema = SearchArgs

    def get_output_jsonschema(self) -> dict:
        return SearchBatch.model_json_schema()

    async def ainvoke(self, arguments: dict) -> dict:
        return {
            "results": [
                {
                    "title": f"result:{arguments['query']}",
                    "url": "https://example.test",
                    "score": 0.9,
                }
            ]
        }


class FakeLangChainTool:
    name = "web_search"
    description = "Search the web."
    args_schema = SearchArgs

    def get_output_jsonschema(self) -> dict:
        return SearchOutput.model_json_schema()

    async def ainvoke(self, arguments: dict) -> dict:
        return {
            "answer": f"result:{arguments['query']}",
            "count": int(arguments.get("limit", 3)),
        }


class FakeLlamaMetadata:
    name = "paper_search"
    description = "Search papers."
    fn_schema = SearchArgs

    def get_name(self) -> str:
        return self.name

    def get_parameters_dict(self) -> dict:
        return self.fn_schema.model_json_schema()


def _paper_fn(query: str, limit: int = 3) -> SearchOutput:
    return SearchOutput(answer=f"paper:{query}", count=limit)


def _paper_batch_fn(query: str, limit: int = 3) -> SearchBatch:
    return SearchBatch(
        results=[
            SearchHit(
                title=f"paper:{query}",
                url="https://arxiv.org/abs/fixture",
                score=0.8,
            )
            for _ in range(limit)
        ]
    )


class FakeLlamaResultsTool:
    metadata = FakeLlamaMetadata()
    real_fn = staticmethod(_paper_batch_fn)

    async def acall(self, **arguments):
        return SimpleNamespace(raw_output=_paper_batch_fn(**arguments))


class FakeLlamaTool:
    metadata = FakeLlamaMetadata()
    real_fn = staticmethod(_paper_fn)

    async def acall(self, **arguments):
        return SimpleNamespace(raw_output=_paper_fn(**arguments))


def test_langchain_import_preserves_declared_input_and_output_contract() -> None:
    spec = tool_from_langchain(
        FakeLangChainTool(),
        provider="search-provider",
        read_only=True,
        remote=True,
    )

    assert spec.provider == "search-provider"
    assert spec.access_mode == "langchain"
    assert spec.remote is True
    endpoint = spec.endpoint("invoke")
    assert endpoint.read_only is True
    assert {parameter.name for parameter in endpoint.parameters} == {"query", "limit"}
    fields = {field.name: field for field in endpoint.output_fields}
    assert fields["answer"].json_schema["type"] == "string"
    assert fields["count"].json_schema["type"] == "integer"


def test_foreign_tool_descriptions_do_not_grant_execution_authority() -> None:
    spec = tool_from_langchain(FakeLangChainTool())

    endpoint = spec.endpoint("invoke")
    assert spec.remote is True
    assert endpoint.read_only is None
    assert endpoint.destructive is None


@pytest.mark.asyncio
async def test_router_executes_imported_langchain_tool_through_normal_pipeline() -> None:
    router = SchemaRouter()
    key = router.add_langchain_tool(
        FakeLangChainTool(),
        provider="tavily",
        read_only=True,
        remote=False,
    )

    plan = router.plan_executable(
        PlanRequest(
            query="web search answer",
            preferred_tools=[key],
            arguments={"query": "SchemaRouter", "limit": 2},
        )
    )
    assert plan.executable
    results = await router.execute(plan)

    assert results[0].tool == key
    assert results[0].data["answer"] == "result:SchemaRouter"


def test_llamaindex_import_uses_tool_metadata_and_typed_return_schema() -> None:
    spec = tool_from_llamaindex(
        FakeLlamaTool(),
        provider="arxiv",
        read_only=True,
        remote=True,
    )

    assert spec.provider == "arxiv"
    assert spec.access_mode == "llamaindex"
    endpoint = spec.endpoint("invoke")
    assert {parameter.name for parameter in endpoint.parameters} == {"query", "limit"}
    fields = {field.name: field for field in endpoint.output_fields}
    assert fields["answer"].json_schema["type"] == "string"
    assert fields["count"].json_schema["type"] == "integer"


@pytest.mark.asyncio
async def test_router_executes_imported_llamaindex_tool_through_normal_pipeline() -> None:
    router = SchemaRouter()
    key = router.add_llamaindex_tool(
        FakeLlamaTool(),
        provider="arxiv",
        read_only=True,
        remote=False,
    )

    plan = router.plan_executable(
        PlanRequest(
            query="paper search answer",
            preferred_tools=[key],
            arguments={"query": "agent routing", "limit": 1},
        )
    )
    assert plan.executable
    results = await router.execute(plan)

    assert results[0].tool == key
    assert results[0].data["answer"] == "paper:agent routing"


def test_langchain_import_exposes_structured_result_array_fields() -> None:
    spec = tool_from_langchain(
        FakeLangChainResultsTool(),
        provider="tavily",
        read_only=True,
        remote=True,
    )
    fields = {field.name: field for field in spec.endpoint("invoke").output_fields}

    assert {
        "results",
        "results[].title",
        "results[].url",
        "results[].score",
    } <= set(fields)
    assert fields["results[].title"].path == ["results", "*", "title"]
    assert fields["results[].title"].result_path == ["results", "*", "title"]


def test_llamaindex_import_exposes_structured_result_array_fields() -> None:
    spec = tool_from_llamaindex(
        FakeLlamaResultsTool(),
        provider="arxiv",
        read_only=True,
        remote=True,
    )
    fields = {field.name: field for field in spec.endpoint("invoke").output_fields}

    assert {
        "results",
        "results[].title",
        "results[].url",
        "results[].score",
    } <= set(fields)
    assert fields["results[].url"].path == ["results", "*", "url"]
    assert fields["results[].url"].result_path == ["results", "*", "url"]


@pytest.mark.asyncio
async def test_web_search_required_optional_and_undeclared_unit_at_execution() -> None:
    """Provider schemas, not global research field assumptions, govern calls."""

    class InstrumentedWebSearch(FakeLangChainTool):
        def __init__(self) -> None:
            self.calls = 0

        async def ainvoke(self, arguments: dict) -> dict:
            self.calls += 1
            return await super().ainvoke(arguments)

    source = InstrumentedWebSearch()
    router = SchemaRouter()
    tool_key = router.add_langchain_tool(
        source, provider="tavily", read_only=True, remote=False,
    )
    spec = router.registry.get(tool_key)
    endpoint = spec.endpoint("invoke")

    # The original Pydantic input schema has ONE required field; "limit"
    # is optional. Neither an input argument nor a provider output has units.
    assert {p.name: p.required for p in endpoint.parameters} == {
        "query": True, "limit": False,
    }
    assert "unit" not in {p.name for p in endpoint.parameters}
    assert endpoint.input_schema["required"] == ["query"]
    assert all(f.unit is None for f in endpoint.output_fields)

    def plan(arguments: dict) -> ExecutionPlan:
        return ExecutionPlan(
            query="web search",
            registry_version=router.registry.version,
            calls=[ToolCall(
                tool=tool_key,
                endpoint="invoke",
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=spec.fingerprint,
                arguments=arguments,
                fields=["answer", "count"],
            )],
        )

    # Optional input is genuinely optional at the execution boundary.
    answer = await router.execute(plan({"query": "SchemaRouter"}))
    assert answer[0].data["answer"] == "result:SchemaRouter"
    assert answer[0].data["count"] == 3
    assert source.calls == 1

    # A required query is missing; no tool invocation occurs.
    with pytest.raises(PlanValidationError, match="missing required arguments"):
        await router.execute(plan({"limit": 2}))
    assert source.calls == 1

    # "unit" does not belong to this web tool, so it cannot be smuggled in
    # as a global argument even when its value looks like valid metadata.
    with pytest.raises(PlanValidationError, match="undeclared arguments"):
        await router.execute(plan({"query": "SchemaRouter", "unit": "°C"}))
    assert source.calls == 1

    # A declared optional argument still has its own JSON Schema type.
    with pytest.raises(SchemaValidationError):
        await router.execute(plan({"query": "SchemaRouter", "limit": "bad"}))
    assert source.calls == 1

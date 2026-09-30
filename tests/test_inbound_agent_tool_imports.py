from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from schemarouter import PlanRequest, SchemaRouter
from schemarouter.integrations import tool_from_langchain, tool_from_llamaindex


class SearchArgs(BaseModel):
    query: str
    limit: int = 3


class SearchOutput(BaseModel):
    answer: str
    count: int


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

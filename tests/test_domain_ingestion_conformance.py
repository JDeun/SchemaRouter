from __future__ import annotations

from pydantic import BaseModel

from schemarouter import tool_from_callable
from schemarouter.integrations import tool_from_langchain


class SearchArgs(BaseModel):
    query: str


class FakeDuckDuckGoTool:
    name = "duckduckgo_search"
    description = "Search the public web."
    args_schema = SearchArgs

    def invoke(self, arguments: dict) -> str:
        return f"result:{arguments['query']}"


class ArxivArgs(BaseModel):
    query: str
    max_results: int = 5


class ArxivResult(BaseModel):
    title: str
    entry_id: str


class FakeArxivTool:
    name = "arxiv_search"
    description = "Search scholarly papers."
    args_schema = ArxivArgs

    def get_output_jsonschema(self) -> dict:
        return ArxivResult.model_json_schema()

    def invoke(self, arguments: dict) -> dict:
        return {
            "title": arguments["query"],
            "entry_id": "arxiv:fixture",
        }


class YahooQuote(BaseModel):
    symbol: str
    price: float
    currency: str


def yahoo_quote(symbol: str) -> YahooQuote:
    return YahooQuote(
        symbol=symbol,
        price=100.0,
        currency="USD",
    )


def test_duckduckgo_shape_compiles_through_agent_tool_import() -> None:
    tool = tool_from_langchain(
        FakeDuckDuckGoTool(),
        provider="duckduckgo",
        access_mode="langchain",
        read_only=True,
        remote=True,
    )

    endpoint = tool.endpoint("invoke")
    assert tool.provider == "duckduckgo"
    assert tool.access_mode == "langchain"
    assert endpoint.read_only is True
    assert [parameter.name for parameter in endpoint.parameters] == ["query"]


def test_arxiv_shape_preserves_declared_scholarly_output_contract() -> None:
    tool = tool_from_langchain(
        FakeArxivTool(),
        provider="arxiv",
        access_mode="langchain",
        read_only=True,
        remote=True,
    )

    endpoint = tool.endpoint("invoke")
    fields = {field.name: field for field in endpoint.output_fields}

    assert {parameter.name for parameter in endpoint.parameters} == {
        "query",
        "max_results",
    }
    assert fields["title"].json_schema["type"] == "string"
    assert fields["entry_id"].json_schema["type"] == "string"
    assert fields["entry_id"].identifier is True


def test_yahoo_finance_shape_compiles_through_typed_python_callable() -> None:
    tool = tool_from_callable(
        yahoo_quote,
        name="yahoo_quote",
        provider="yahoo-finance",
        access_mode="python",
    )

    endpoint = tool.endpoint("call")
    fields = {field.name: field for field in endpoint.output_fields}

    assert tool.provider == "yahoo-finance"
    assert tool.access_mode == "python"
    assert [parameter.name for parameter in endpoint.parameters] == ["symbol"]
    assert fields["symbol"].json_schema["type"] == "string"
    assert fields["price"].json_schema["type"] == "number"
    assert fields["currency"].json_schema["type"] == "string"

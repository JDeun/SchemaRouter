"""Minimal runnable LangChain integration example."""

from schemarouter import SchemaRouter, schema_tool
from schemarouter.integrations import to_langchain_tool


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers through the SchemaRouter execution boundary."""
    return a + b


def main() -> None:
    router = SchemaRouter()
    router.add_callable(add)

    tool = to_langchain_tool(router, "add", "call")
    result = tool.invoke({"a": 2, "b": 3})

    assert result == 5
    print(result)


if __name__ == "__main__":
    main()

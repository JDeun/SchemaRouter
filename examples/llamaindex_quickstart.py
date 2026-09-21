"""Minimal runnable LlamaIndex integration example."""

from schemarouter import SchemaRouter, schema_tool
from schemarouter.integrations import to_llamaindex_tool


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers through the SchemaRouter execution boundary."""
    return a + b


def main() -> None:
    router = SchemaRouter()
    router.add_callable(add)

    tool = to_llamaindex_tool(router, "add", "call")
    result = tool(a=2, b=3)

    assert result.raw_output == 5
    print(result.raw_output)


if __name__ == "__main__":
    main()

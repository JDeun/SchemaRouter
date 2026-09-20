from pydantic import BaseModel
import pytest

from schemarouter import (
    PlanRequest,
    RegistrationError,
    SchemaRouter,
    schema_tool,
    tool_from_callable,
)


class WeatherResult(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str, units: str = "metric") -> WeatherResult:
    """Return the current weather."""
    return WeatherResult(city=city, temperature=20.5)


def test_tool_from_callable_derives_input_and_output_schemas() -> None:
    tool = tool_from_callable(current_weather)
    endpoint = tool.endpoints[0]

    assert tool.name == "current_weather"
    assert endpoint.name == "call"
    assert endpoint.input_schema["type"] == "object"
    assert endpoint.input_schema["required"] == ["city"]
    assert endpoint.input_schema["properties"]["city"]["type"] == "string"
    assert endpoint.input_schema["properties"]["units"]["type"] == "string"
    assert set(field.name for field in endpoint.output_fields) == {
        "city",
        "temperature",
    }


def test_add_callable_uses_decorator_metadata_and_executes() -> None:
    router = SchemaRouter()
    key = router.add_callable(current_weather)

    assert key == "current_weather"
    endpoint = router.registry.endpoint(key, "call")
    assert endpoint.read_only is True

    result = router.invoke(
        PlanRequest(
            query="current weather temperature",
            arguments={"city": "Seoul"},
        )
    )

    assert result[0].data == {
        "city": "Seoul",
        "temperature": 20.5,
    }


@pytest.mark.asyncio
async def test_add_callable_supports_async_functions() -> None:
    async def lookup(user_id: int) -> dict[str, str]:
        return {"user_id": str(user_id)}

    router = SchemaRouter()
    router.add_callable(lookup, read_only=True)

    result = await router.ainvoke(
        PlanRequest(
            query="lookup user",
            arguments={"user_id": 42},
        )
    )

    assert result[0].data == {"user_id": "42"}


def test_callable_argument_types_are_runtime_validated() -> None:
    router = SchemaRouter()
    router.add_callable(current_weather)

    with pytest.raises(Exception, match="arguments for current_weather.call"):
        router.invoke(
            PlanRequest(
                query="current weather",
                arguments={"city": 123},
            )
        )


def test_variadic_callable_requires_explicit_contract() -> None:
    def variadic(*values: int) -> int:
        return sum(values)

    with pytest.raises(RegistrationError, match="variadic"):
        tool_from_callable(variadic)


def test_positional_only_callable_requires_explicit_contract() -> None:
    namespace = {}
    exec(
        "def positional(value: int, /) -> int:\n"
        "    return value\n",
        namespace,
    )
    positional = namespace["positional"]

    with pytest.raises(RegistrationError, match="positional-only"):
        tool_from_callable(positional)

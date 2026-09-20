"""Offline SchemaRouter quickstart used as both documentation and a CI smoke test."""

from pydantic import BaseModel

from schemarouter import PlanRequest, SchemaRouter, schema_tool


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    """Return a deterministic example weather observation."""
    return Weather(city=city, temperature=20.5)


def main() -> None:
    router = SchemaRouter()
    router.add_callable(current_weather)

    results = router.invoke(
        PlanRequest(
            query="city temperature",
            arguments={"city": "Seoul"},
        )
    )
    assert results[0].data == {
        "city": "Seoul",
        "temperature": 20.5,
    }
    print(results[0].data)


if __name__ == "__main__":
    main()

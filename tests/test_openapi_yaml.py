import httpx
import pytest

from schemarouter import SchemaRouter


@pytest.mark.asyncio
async def test_openapi_yaml_timestamp_scalars_remain_json_strings() -> None:
    document = """openapi: 3.1.0
info:
  title: Timestamp API
paths:
  /event:
    get:
      operationId: get_event
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  created_at:
                    type: string
                    format: date-time
                    default: 2025-01-02T03:04:05Z
                  event_date:
                    type: string
                    format: date
                    enum:
                      - 2025-01-02
"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://docs.example.test/openapi.yaml")
        return httpx.Response(
            200,
            text=document,
            headers={"content-type": "application/yaml"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://docs.example.test/openapi.yaml",
            kind="openapi",
            http_client=client,
        )

    endpoint = router.registry.get("timestamp_api").endpoint("get_event")
    fields = {field.name: field for field in endpoint.output_fields}

    assert fields["created_at"].json_schema["default"] == "2025-01-02T03:04:05Z"
    assert fields["event_date"].json_schema["enum"] == ["2025-01-02"]

import httpx
import pytest

from schemarouter import SchemaRouter
from schemarouter.document_loading import DEFAULT_YAML_MAX_ALIASES
from schemarouter.errors import SchemaSourceError


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


def _openapi_yaml_with_aliases(alias_count: int) -> str:
    aliases = "\n".join("  - *shared" for _ in range(alias_count))
    return f"""openapi: 3.1.0
info:
  title: Alias API
x-shared: &shared
  type: object
  properties:
    id:
      type: string
x-aliases:
{aliases}
paths:
  /items:
    get:
      operationId: list_items
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
"""


@pytest.mark.asyncio
async def test_openapi_yaml_allows_ordinary_aliases_within_budget() -> None:
    document = _openapi_yaml_with_aliases(1)

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

    assert router.registry.get("alias_api").endpoint("list_items").name == "list_items"


@pytest.mark.asyncio
async def test_openapi_yaml_rejects_alias_fanout_before_construction() -> None:
    document = _openapi_yaml_with_aliases(DEFAULT_YAML_MAX_ALIASES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=document,
            headers={"content-type": "application/yaml"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SchemaSourceError, match="YAML alias limit exceeded"):
            await SchemaRouter.from_url(
                "https://docs.example.test/openapi.yaml",
                kind="openapi",
                http_client=client,
            )


@pytest.mark.asyncio
async def test_openapi_yaml_rejects_cyclic_alias_graph_before_normalization() -> None:
    document = """openapi: 3.1.0
info:
  title: Cyclic Alias API
x-cycle: &cycle
  self: *cycle
paths:
  /items:
    get:
      operationId: list_items
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=document,
            headers={"content-type": "application/yaml"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SchemaSourceError, match="cyclic container graph"):
            await SchemaRouter.from_url(
                "https://docs.example.test/openapi.yaml",
                kind="openapi",
                http_client=client,
            )

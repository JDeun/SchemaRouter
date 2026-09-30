from __future__ import annotations

import httpx
import pytest

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall
from schemarouter.adapters import tool_from_odata_metadata


METADATA = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx
  xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"
  Version="4.0">
  <edmx:DataServices>
    <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="Demo">
      <ComplexType Name="Address">
        <Property Name="City" Type="Edm.String" Nullable="false" />
        <Property Name="Zip" Type="Edm.String" />
      </ComplexType>
      <EntityType Name="Product">
        <Key>
          <PropertyRef Name="ID" />
        </Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false" />
        <Property Name="Name" Type="Edm.String" Nullable="false" />
        <Property Name="Price" Type="Edm.Decimal" />
        <Property Name="Address" Type="Demo.Address" />
      </EntityType>
      <EntityContainer Name="DefaultContainer">
        <EntitySet Name="Products" EntityType="Demo.Product" />
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def test_odata_metadata_compiles_entity_fields_and_complex_paths() -> None:
    tool = tool_from_odata_metadata("demo", METADATA)

    endpoint = tool.endpoint("list_products")
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    assert endpoint.path == "/Products"

    fields = {field.name: field for field in endpoint.output_fields}
    assert {"ID", "Name", "Price", "Address", "Address.City", "Address.Zip"} <= set(
        fields
    )
    assert fields["ID"].identifier is True
    assert fields["ID"].json_schema["type"] == "integer"
    assert fields["Address.City"].path == ["Address", "City"]
    assert fields["Address.City"].result_path == ["Address.City"]
    assert fields["Address.City"].source_type == "odata"

    assert endpoint.server_projection is not None
    assert endpoint.server_projection.selector_for(fields["ID"]) == "ID"
    assert endpoint.server_projection.selector_for(
        fields["Address.City"]
    ) == "Address/City"


@pytest.mark.asyncio
async def test_odata_selected_fields_become_select_and_project_records() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/$metadata"):
            return httpx.Response(
                200,
                content=METADATA,
                headers={"content-type": "application/xml"},
                request=request,
            )

        assert request.url.path == "/odata/Products"
        seen_queries.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "ID": 1,
                        "Address": {
                            "City": "Suwon",
                        },
                    },
                    {
                        "ID": 2,
                        "Address": {
                            "City": "Seoul",
                        },
                    },
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata",
            kind="odata",
            http_client=client,
        )
        tool = router.registry.get("odata.example")
        endpoint = tool.endpoint("list_products")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            fields=["ID", "Address.City"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="product city",
            registry_version=router.registry.version,
            calls=[call],
        )
        results = await router.execute(plan)

    assert seen_queries == [{"$select": "ID,Address/City"}]
    assert results[0].data == [
        {"ID": 1, "Address.City": "Suwon"},
        {"ID": 2, "Address.City": "Seoul"},
    ]


@pytest.mark.asyncio
async def test_odata_query_options_remain_typed_and_server_owned() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/$metadata"):
            return httpx.Response(200, content=METADATA, request=request)

        seen_queries.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "ID": 1,
                        "Name": "A",
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata",
            kind="odata",
            http_client=client,
        )
        tool = router.registry.get("odata.example")
        endpoint = tool.endpoint("list_products")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={
                "filter": "Price gt 10",
                "orderby": "Name asc",
                "top": 5,
                "skip": 0,
            },
            fields=["ID", "Name"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="filtered products",
            registry_version=router.registry.version,
            calls=[call],
        )
        await router.execute(plan)

    assert seen_queries == [
        {
            "$filter": "Price gt 10",
            "$orderby": "Name asc",
            "$top": "5",
            "$skip": "0",
            "$select": "ID,Name",
        }
    ]


def test_odata_metadata_rejects_dtd_and_entity_declarations() -> None:
    malicious = b"""<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo/>"""

    with pytest.raises(Exception, match="DTD/entity"):
        tool_from_odata_metadata("bad", malicious)

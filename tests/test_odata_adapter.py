from __future__ import annotations

import httpx
import pytest

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall
from schemarouter.adapters import tool_from_odata_metadata


METADATA = b"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0"
  xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="Demo"
      xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <ComplexType Name="Address">
        <Property Name="City" Type="Edm.String" Nullable="false" />
        <Property Name="Country" Type="Edm.String" />
      </ComplexType>
      <EntityType Name="Product">
        <Key><PropertyRef Name="ID" /></Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false" />
        <Property Name="Name" Type="Edm.String" Nullable="false" />
        <Property Name="Price" Type="Edm.Decimal">
          <Annotation Term="Org.OData.Measures.V1.ISOCurrency" String="USD" />
        </Property>
        <Property Name="Address" Type="Demo.Address" />
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Products" EntityType="Demo.Product" />
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def test_odata_metadata_compiles_entity_fields_and_complex_paths() -> None:
    tool = tool_from_odata_metadata("demo", METADATA)

    endpoint = tool.endpoint("list_products")
    fields = {field.name: field for field in endpoint.output_fields}

    assert endpoint.read_only is True
    assert endpoint.server_projection is not None
    assert endpoint.server_projection.parameter == "$select"
    assert {"ID", "Name", "Price", "Address", "Address.City", "Address.Country"} <= set(
        fields
    )
    assert fields["ID"].identifier is True
    assert fields["Price"].unit == "USD"
    assert fields["Address.City"].path == ["Address", "City"]
    assert fields["Address.City"].result_path == ["Address.City"]
    assert endpoint.server_projection.field_map["Address.City"] == "Address/City"
    assert endpoint.output_schema["type"] == "array"


@pytest.mark.asyncio
async def test_odata_discovery_execution_and_select_projection() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/odata/$metadata":
            return httpx.Response(
                200,
                content=METADATA,
                headers={"content-type": "application/xml"},
                request=request,
            )
        if request.url.path == "/odata/Products":
            seen_queries.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "@odata.context": "$metadata#Products",
                    "value": [
                        {
                            "ID": 1,
                            "Name": "Sample",
                            "Price": 12.5,
                            "Address": {
                                "City": "Suwon",
                                "Country": "KR",
                            },
                        }
                    ],
                },
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

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
            arguments={"filter": "Price gt 10", "top": 5},
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

    assert seen_queries == [
        {
            "$filter": "Price gt 10",
            "$top": "5",
            "$select": "ID,Address/City",
        }
    ]
    assert results[0].data == [
        {
            "ID": 1,
            "Address.City": "Suwon",
        }
    ]


@pytest.mark.asyncio
async def test_odata_metadata_url_is_accepted_directly() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path == "/odata/$metadata":
            return httpx.Response(200, content=METADATA, request=request)
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata/$metadata",
            kind="odata",
            http_client=client,
        )

    assert requested == ["/odata/$metadata"]
    assert router.registry.get("odata.example").metadata["adapter"] == "odata"


def test_odata_metadata_rejects_dtd_entities() -> None:
    malicious = b"""<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <foo>&xxe;</foo>"""

    with pytest.raises(Exception, match="DTD/entity"):
        tool_from_odata_metadata("bad", malicious)

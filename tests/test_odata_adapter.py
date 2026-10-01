from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    ExecutionPlan,
    InvocationUnavailableError,
    NonRetryableInvocationError,
    SchemaRouter,
    SchemaSourceError,
    ToolCall,
    tool_from_odata_metadata,
)
from schemarouter.adapters.odata import (
    ODataRemoteInvoker,
    _validate_base_url,
)

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
      <ComplexType Name="Measurement">
        <Property Name="Value" Type="Edm.Double">
          <Annotation Term="Org.OData.Measures.V1.Unit" String="eV" />
        </Property>
        <Property Name="Method" Type="Edm.String" />
      </ComplexType>
      <EntityType Name="Product">
        <Key><PropertyRef Name="ID" /></Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false" />
        <Property Name="Name" Type="Edm.String" Nullable="false" />
        <Property Name="Price" Type="Edm.Decimal">
          <Annotation
            Term="Org.OData.Measures.V1.ISOCurrency"
            String="USD"
          />
        </Property>
        <Property Name="Address" Type="Demo.Address" />
        <Property Name="Measurements" Type="Collection(Demo.Measurement)" />
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Products" EntityType="Demo.Product" />
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def test_odata_metadata_compiles_fields_units_and_complex_paths() -> None:
    tool = tool_from_odata_metadata("demo", METADATA)

    endpoint = tool.endpoint("list_products")
    fields = {field.name: field for field in endpoint.output_fields}

    assert endpoint.read_only is True
    assert endpoint.server_projection is not None
    assert endpoint.server_projection.parameter == "$select"
    assert {
        "ID",
        "Name",
        "Price",
        "Address",
        "Address.City",
        "Address.Country",
        "Measurements",
        "Measurements[].Value",
        "Measurements[].Method",
    } <= set(fields)
    assert fields["ID"].identifier is True
    assert fields["Price"].unit == "USD"
    assert fields["Address.City"].path == ["Address", "City"]
    assert fields["Address.City"].result_path == ["Address.City"]
    assert fields["Address.City"].source_type == "odata"
    assert endpoint.server_projection.field_map["Address.City"] == "Address/City"
    assert fields["Measurements[].Value"].path == ["Measurements", "*", "Value"]
    assert fields["Measurements[].Value"].result_path == ["Measurements", "*", "Value"]
    assert fields["Measurements[].Value"].unit == "eV"
    assert (
        endpoint.server_projection.field_map["Measurements[].Value"]
        == "Measurements/Value"
    )
    assert endpoint.output_schema["type"] == "array"


@pytest.mark.asyncio
async def test_odata_selected_fields_become_select_and_project_records() -> None:
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
                            "Address": {
                                "City": "Suwon",
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
async def test_odata_filter_orderby_top_and_skip_use_wire_names() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/odata/$metadata":
            return httpx.Response(200, content=METADATA, request=request)
        if request.url.path == "/odata/Products":
            seen_queries.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={"value": [{"ID": 1}]},
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata/$metadata",
            kind="odata",
            http_client=client,
        )
        tool = router.registry.get("odata.example")
        endpoint = tool.endpoint("list_products")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={
                "filter": "Name eq 'Sample'",
                "orderby": "ID asc",
                "top": 1,
                "skip": 0,
            },
            fields=["ID"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="one product",
            registry_version=router.registry.version,
            calls=[call],
        )
        await router.execute(plan)

    assert seen_queries == [
        {
            "$filter": "Name eq 'Sample'",
            "$orderby": "ID asc",
            "$top": "1",
            "$skip": "0",
            "$select": "ID",
        }
    ]


@pytest.mark.asyncio
async def test_odata_schema_and_runtime_headers_are_separated() -> None:
    seen_metadata_auth: list[str | None] = []
    seen_runtime_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/odata/$metadata":
            seen_metadata_auth.append(request.headers.get("authorization"))
            return httpx.Response(200, content=METADATA, request=request)
        if request.url.path == "/odata/Products":
            seen_runtime_auth.append(request.headers.get("authorization"))
            return httpx.Response(
                200,
                json={"value": [{"ID": 1}]},
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    schema_token = "Bearer schema-secret"
    runtime_token = "Bearer runtime-secret"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = await SchemaRouter.from_url(
            "https://odata.example/odata",
            kind="odata",
            schema_headers={"Authorization": schema_token},
            trusted_headers={"Authorization": runtime_token},
            http_client=client,
        )
        tool = router.registry.get("odata.example")
        endpoint = tool.endpoint("list_products")
        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"top": 1},
            fields=["ID"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="one product",
            registry_version=router.registry.version,
            calls=[call],
        )
        await router.execute(plan)

    assert seen_metadata_auth == [schema_token]
    assert seen_runtime_auth == [runtime_token]
    serialized = repr(
        router.registry.get("odata.example").model_dump(mode="json")
    )
    assert "schema-secret" not in serialized
    assert "runtime-secret" not in serialized


def test_odata_metadata_rejects_dtd_entities() -> None:
    malicious = b"""<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <foo>&xxe;</foo>"""

    with pytest.raises(Exception, match="DTD/entity"):
        tool_from_odata_metadata("bad", malicious)


@pytest.mark.parametrize(
    "url, message",
    [
        ("relative/path", "absolute http"),
        ("ftp://odata.example/service", "absolute http"),
        ("https://user:pass@odata.example/service", "must not contain credentials"),
        ("https://odata.example/service?x=1", "query or fragment"),
        ("https://odata.example/service#frag", "query or fragment"),
    ],
)
def test_odata_service_url_validation(url: str, message: str) -> None:
    with pytest.raises(SchemaSourceError, match=message):
        _validate_base_url(url)


def test_odata_metadata_rejects_invalid_xml() -> None:
    with pytest.raises(SchemaSourceError, match="not valid XML"):
        tool_from_odata_metadata("bad", b"<not-closed>")


def test_odata_metadata_rejects_document_without_types() -> None:
    metadata = b"""<?xml version="1.0"?>
    <edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
      <edmx:DataServices>
        <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"
                Namespace="Empty">
          <EntityContainer Name="Container" />
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>
    """
    with pytest.raises(SchemaSourceError, match="no entity/complex types"):
        tool_from_odata_metadata("empty", metadata)


def test_odata_metadata_rejects_types_without_usable_entity_sets() -> None:
    metadata = b"""<?xml version="1.0"?>
    <edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
      <edmx:DataServices>
        <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"
                Namespace="Demo">
          <EntityType Name="Product">
            <Property Name="ID" Type="Edm.Int32" />
          </EntityType>
          <EntityContainer Name="Container">
            <EntitySet Name="Broken" EntityType="Demo.Missing" />
          </EntityContainer>
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>
    """
    with pytest.raises(SchemaSourceError, match="no usable entity sets"):
        tool_from_odata_metadata("empty", metadata)


def test_odata_collection_types_and_descriptions_are_preserved() -> None:
    metadata = b"""<?xml version="1.0"?>
    <edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
      <edmx:DataServices>
        <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"
                Namespace="Demo">
          <ComplexType Name="Address">
            <Property Name="City" Type="Edm.String" />
          </ComplexType>
          <EntityType Name="Product">
            <Property Name="Tags" Type="Collection(Edm.String)" />
            <Property Name="Addresses" Type="Collection(Demo.Address)" />
            <Property Name="Score" Type="Edm.Double">
              <Annotation Term="Org.OData.Core.V1.Description"
                          String="  Model score  " />
              <Annotation Term="Org.OData.Measures.V1.Unit"
                          String="  eV  " />
            </Property>
          </EntityType>
          <EntityContainer Name="Container">
            <EntitySet Name="Products" EntityType="Demo.Product" />
          </EntityContainer>
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>
    """
    tool = tool_from_odata_metadata("demo", metadata)
    fields = {
        field.name: field
        for field in tool.endpoint("list_products").output_fields
    }

    assert fields["Tags"].json_schema["type"] == "array"
    assert fields["Tags"].json_schema["items"]["type"] == "string"
    assert fields["Addresses"].json_schema["type"] == "array"
    assert fields["Addresses"].json_schema["items"]["type"] == "object"
    assert "Addresses[].City" in fields
    assert fields["Addresses[].City"].path == ["Addresses", "*", "City"]
    assert fields["Score"].description == "Model score"
    assert fields["Score"].unit == "eV"


@pytest.mark.asyncio
async def test_odata_metadata_redirect_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://other.example/$metadata"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(SchemaSourceError, match="redirects"):
            await SchemaRouter.from_url(
                "https://odata.example/odata",
                kind="odata",
                http_client=client,
            )


@pytest.mark.asyncio
async def test_odata_metadata_declared_size_limit_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": str(6 * 1024 * 1024)},
            content=b"<metadata />",
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(SchemaSourceError, match="byte safety limit"):
            await SchemaRouter.from_url(
                "https://odata.example/odata",
                kind="odata",
                http_client=client,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, error_type, message",
    [
        (429, InvocationUnavailableError, "temporarily unavailable"),
        (503, InvocationUnavailableError, "temporarily unavailable"),
        (400, NonRetryableInvocationError, "failed with HTTP 400"),
    ],
)
async def test_odata_invoker_classifies_http_failures(
    status: int,
    error_type: type[Exception],
    message: str,
) -> None:
    tool = tool_from_odata_metadata("demo", METADATA)
    endpoint = tool.endpoint("list_products")
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=["ID"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        invoker = ODataRemoteInvoker(
            tool,
            "https://odata.example/odata",
            http_client=client,
        )
        with pytest.raises(error_type, match=message):
            await invoker.invoke_call(call)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content, expected",
    [
        (b"not-json", "not valid JSON"),
        (b"[]", "must be a JSON object"),
        (b"{}", "missing value"),
        (b'{"value": {}}', "missing value"),
    ],
)
async def test_odata_invoker_rejects_invalid_collection_payloads(
    content: bytes,
    expected: str,
) -> None:
    tool = tool_from_odata_metadata("demo", METADATA)
    endpoint = tool.endpoint("list_products")
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=["ID"],
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "application/json"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        invoker = ODataRemoteInvoker(
            tool,
            "https://odata.example/odata",
            http_client=client,
        )
        with pytest.raises(NonRetryableInvocationError, match=expected):
            await invoker.invoke_call(call)


@pytest.mark.asyncio
async def test_odata_source_adapter_rejects_explicit_base_url_override() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("base_url rejection must happen before network access")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(SchemaSourceError, match="base_url is not valid"):
            await SchemaRouter.from_url(
                "https://odata.example/odata",
                kind="odata",
                base_url="https://other.example/odata",
                http_client=client,
            )


@pytest.mark.asyncio
async def test_odata_nested_collection_projection_preserves_record_alignment() -> None:
    seen_queries: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/odata/$metadata":
            return httpx.Response(200, content=METADATA, request=request)
        if request.url.path == "/odata/Products":
            seen_queries.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "ID": 1,
                            "Measurements": [
                                {"Value": 1.1, "Method": "A"},
                                {"Value": 2.2, "Method": "B"},
                            ],
                        }
                    ]
                },
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

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
            fields=["ID", "Measurements[].Value", "Measurements[].Method"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="measurement values and methods",
            registry_version=router.registry.version,
            calls=[call],
        )
        result = (await router.execute(plan))[0]

    assert seen_queries == [
        {
            "$select": "ID,Measurements/Value,Measurements/Method",
        }
    ]
    assert result.data == [
        {
            "ID": 1,
            "Measurements": [
                {"Value": 1.1, "Method": "A"},
                {"Value": 2.2, "Method": "B"},
            ],
        }
    ]

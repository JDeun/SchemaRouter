from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    fields: list[str],
    arguments: dict[str, object] | None = None,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("query")
    return ExecutionPlan(
        query=f"query {tool_key}",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments or {},
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


class FakeCosmosContainer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.row = {
            "id": "doc-1",
            "department": "engineering",
            "title": "Router",
            "timestamp": "2026-10-04T00:00:00Z",
        }

    def query_items(self, **kwargs: Any):
        self.calls.append(dict(kwargs))
        return [dict(self.row)]


class FakeCosmosDatabase:
    def __init__(self) -> None:
        self.container = FakeCosmosContainer()

    def list_containers(self):
        return [{"id": "documents"}]

    def get_container_client(self, name: str) -> FakeCosmosContainer:
        assert name == "documents"
        return self.container


@pytest.mark.asyncio
async def test_cosmos_native_adapter_discovers_and_parameterizes_queries() -> None:
    database = FakeCosmosDatabase()
    router = SchemaRouter()
    keys = await router.aadd_cosmos_record_store(
        database,
        database_name="cosmos",
        time_field_by_container={"documents": "timestamp"},
        remote=False,
    )
    assert keys == ("cosmos.documents",)

    result = await router.execute(
        _plan(
            router,
            "cosmos.documents",
            fields=["id", "title"],
            arguments={
                "filter__department": "engineering",
                "start_time": "2026-10-03T00:00:00Z",
                "end_time": "2026-10-05T00:00:00Z",
                "limit": 5,
            },
        )
    )
    assert result[0].data == [{"id": "doc-1", "title": "Router"}]
    call = database.container.calls[-1]
    assert "OFFSET 0 LIMIT @limit" in call["query"]
    assert "engineering" not in call["query"]
    parameters = {item["name"]: item["value"] for item in call["parameters"]}
    assert parameters["@p0"] == "engineering"
    assert parameters["@limit"] == 5


class FakeCouchbaseResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def rows(self):
        return iter(self._rows)


class FakeCouchbaseCluster:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, statement: str, **kwargs: Any) -> FakeCouchbaseResult:
        self.calls.append((statement, dict(kwargs)))
        if "system:keyspaces" in statement:
            return FakeCouchbaseResult(
                [{"bucket": "travel", "scope": "inventory", "name": "airport"}]
            )
        if "LIMIT 1" in statement:
            return FakeCouchbaseResult(
                [{"id": "airport-1", "city": "Seoul", "country": "KR"}]
            )
        return FakeCouchbaseResult(
            [{"id": "airport-1", "city": "Seoul", "country": "KR"}]
        )


@pytest.mark.asyncio
async def test_couchbase_native_adapter_discovers_keyspaces_and_uses_named_parameters() -> None:
    cluster = FakeCouchbaseCluster()
    router = SchemaRouter()
    keys = await router.aadd_couchbase_record_store(
        cluster,
        database_name="cb",
        remote=False,
    )
    assert keys == ("cb.travel_inventory_airport",)

    result = await router.execute(
        _plan(
            router,
            "cb.travel_inventory_airport",
            fields=["id", "city"],
            arguments={"filter__country": "KR", "limit": 4},
        )
    )
    assert result[0].data == [{"id": "airport-1", "city": "Seoul"}]
    statement, params = cluster.calls[-1]
    assert "SELECT RAW c" in statement
    assert "c." in statement
    assert "$p0" in statement
    assert params["p0"] == "KR"
    assert params["limit"] == 4


class FakeClickHouseResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.result_set = rows


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def query(
        self,
        statement: str,
        parameters: dict[str, Any] | None = None,
    ) -> FakeClickHouseResult:
        self.calls.append((statement, None if parameters is None else dict(parameters)))
        if "system.tables" in statement:
            return FakeClickHouseResult([("analytics", "events")])
        if statement.startswith("DESCRIBE TABLE"):
            return FakeClickHouseResult(
                [
                    ("timestamp", "DateTime", "", "", "", "", ""),
                    ("service", "String", "", "", "", "", ""),
                    ("value", "Float64", "", "", "", "", ""),
                ]
            )
        return FakeClickHouseResult(
            [(dt.datetime(2026, 10, 4, 0, 0), "router", 42.5)]
        )


@pytest.mark.asyncio
async def test_clickhouse_native_adapter_introspects_and_binds_parameters() -> None:
    client = FakeClickHouseClient()
    router = SchemaRouter()
    keys = await router.aadd_clickhouse_record_store(
        client,
        database_name="click",
        time_field_by_table={"analytics.events": "timestamp"},
        remote=False,
    )
    assert keys == ("click.analytics_events",)

    result = await router.execute(
        _plan(
            router,
            "click.analytics_events",
            fields=["timestamp", "service", "value"],
            arguments={
                "filter__service": "router",
                "start_time": "2026-10-03 00:00:00",
                "end_time": "2026-10-05 00:00:00",
                "limit": 9,
            },
        )
    )
    assert result[0].data[0]["service"] == "router"
    assert result[0].data[0]["value"] == 42.5
    statement, params = client.calls[-1]
    assert "{p0:String}" in statement
    assert "{start:DateTime}" in statement
    assert "{end:DateTime}" in statement
    assert "LIMIT {limit:UInt64}" in statement
    assert params == {
        "limit": 9,
        "p0": "router",
        "start": "2026-10-03 00:00:00",
        "end": "2026-10-05 00:00:00",
    }


class FakeFluxRecord:
    def __init__(
        self,
        value: Any,
        *,
        field: str | None = None,
        time: dt.datetime | None = None,
        values: dict[str, Any] | None = None,
    ) -> None:
        self._value = value
        self._field = field
        self._time = time
        self.values = values or {}

    def get_value(self) -> Any:
        return self._value

    def get_field(self) -> str | None:
        return self._field

    def get_time(self) -> dt.datetime | None:
        return self._time


class FakeFluxTable:
    def __init__(self, records: list[FakeFluxRecord]) -> None:
        self.records = records


class FakeInfluxQueryApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def query(self, *, org: str, query: str):
        self.calls.append((org, query))
        if "schema.measurements" in query:
            return [FakeFluxTable([FakeFluxRecord("cpu")])]
        if "schema.fieldKeys" in query:
            return [FakeFluxTable([FakeFluxRecord("usage")])]
        if "schema.tagKeys" in query:
            return [
                FakeFluxTable(
                    [
                        FakeFluxRecord("_measurement"),
                        FakeFluxRecord("host"),
                    ]
                )
            ]
        return [
            FakeFluxTable(
                [
                    FakeFluxRecord(
                        17.5,
                        field="usage",
                        time=dt.datetime(2026, 10, 4, 0, 0),
                        values={"host": "server-1"},
                    )
                ]
            )
        ]


@pytest.mark.asyncio
async def test_influxdb_native_adapter_discovers_schema_and_compiles_flux() -> None:
    query_api = FakeInfluxQueryApi()
    router = SchemaRouter()
    keys = await router.aadd_influxdb_record_store(
        query_api,
        bucket="metrics",
        org="acme",
        database_name="influx",
        remote=False,
    )
    assert keys == ("influx.cpu",)

    result = await router.execute(
        _plan(
            router,
            "influx.cpu",
            fields=["timestamp", "field", "value", "host"],
            arguments={
                "filter__field": "usage",
                "filter__host": "server-1",
                "start_time": "2026-10-03T00:00:00Z",
                "end_time": "2026-10-05T00:00:00Z",
                "limit": 3,
            },
        )
    )
    assert result[0].data == [
        {
            "timestamp": "2026-10-04T00:00:00",
            "field": "usage",
            "value": 17.5,
            "host": "server-1",
        }
    ]
    org, flux = query_api.calls[-1]
    assert org == "acme"
    assert 'from(bucket: "metrics")' in flux
    assert 'r._measurement == "cpu"' in flux
    assert 'r._field == "usage"' in flux
    assert 'r["host"] == "server-1"' in flux
    assert "|> limit(n: 3)" in flux

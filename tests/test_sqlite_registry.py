import json
import sqlite3

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    RegistrationError,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
)


def tool(name: str, *, field_name: str = "value") -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} tool",
        endpoints=[
            EndpointSpec(
                name="get",
                parameters=[ParameterSpec(name="id", required=True)],
                output_fields=[FieldSpec(name=field_name)],
                output_schema={
                    "type": "object",
                    "properties": {field_name: {"type": "string"}},
                },
                read_only=True,
            )
        ],
        source_type="test",
        metadata={"owner": "tests"},
    )


def test_sqlite_registry_persists_tools_version_and_order(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        assert registry.version == 0
        registry.register(tool("alpha"))
        registry.register(tool("beta"))
        assert registry.version == 2
        assert registry.keys() == ("alpha", "beta")

    with SQLiteRegistry(path) as reopened:
        assert reopened.version == 2
        assert reopened.keys() == ("alpha", "beta")
        assert [item.name for item in reopened.tools()] == ["alpha", "beta"]
        assert reopened.endpoint("alpha", "get").name == "get"


def test_sqlite_registry_returns_detached_models(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.register(tool("alpha"))
        snapshot = registry.get("alpha")
        snapshot.description = "mutated outside registry"
        snapshot.endpoints[0].output_fields.append(FieldSpec(name="extra"))

        persisted = registry.get("alpha")
        assert persisted.description == "alpha tool"
        assert [field.name for field in persisted.endpoints[0].output_fields] == ["value"]


def test_sqlite_registry_replace_keeps_position_and_bumps_once(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.update_many([tool("alpha"), tool("beta")])
        assert registry.version == 1

        replacement = tool("alpha", field_name="updated")
        registry.register(replacement, replace=True)

        assert registry.version == 2
        assert registry.keys() == ("alpha", "beta")
        assert [
            field.name for field in registry.endpoint("alpha", "get").output_fields
        ] == ["updated"]


def test_sqlite_registry_unregister_persists(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.update_many([tool("alpha"), tool("beta")])
        registry.unregister("alpha")
        assert registry.version == 2
        assert registry.keys() == ("beta",)

    with SQLiteRegistry(path) as reopened:
        assert reopened.version == 2
        assert reopened.keys() == ("beta",)
        with pytest.raises(KeyError):
            reopened.get("alpha")


def test_sqlite_registry_failed_collision_rolls_back_batch_and_version(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.register(tool("alpha"))
        before_version = registry.version

        with pytest.raises(RegistrationError, match="already registered"):
            registry.update_many([tool("beta"), tool("alpha")])

        assert registry.version == before_version
        assert registry.keys() == ("alpha",)


def test_sqlite_registry_duplicate_batch_fails_before_write(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        with pytest.raises(RegistrationError, match="duplicate tool keys"):
            registry.update_many([tool("alpha"), tool("alpha")])

        assert registry.version == 0
        assert registry.keys() == ()


def test_sqlite_registry_multiple_instances_observe_committed_changes(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as first, SQLiteRegistry(path) as second:
        first.register(tool("alpha"))

        assert second.version == 1
        assert second.keys() == ("alpha",)

        second.register(tool("beta"))

        assert first.version == 2
        assert first.keys() == ("alpha", "beta")


def test_sqlite_registry_corrupt_document_fails_closed(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.register(tool("alpha"))

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE schemarouter_registry_tools SET document = ? WHERE key = ?",
            ('{"name":"wrong","endpoints":[]}', "alpha"),
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteRegistry(path) as reopened:
        with pytest.raises(RegistrationError, match="not a valid ToolSpec"):
            reopened.get("alpha")


def test_sqlite_registry_key_mismatch_fails_closed(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.register(tool("alpha"))

    connection = sqlite3.connect(path)
    try:
        mismatched = tool("beta").model_dump_json()
        connection.execute(
            "UPDATE schemarouter_registry_tools SET document = ? WHERE key = ?",
            (mismatched, "alpha"),
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteRegistry(path) as reopened:
        with pytest.raises(RegistrationError, match="key mismatch"):
            reopened.get("alpha")


def test_sqlite_registry_rejects_operations_after_close(tmp_path) -> None:
    registry = SQLiteRegistry(tmp_path / "registry.sqlite3")
    registry.close()
    registry.close()

    with pytest.raises(RuntimeError, match="closed"):
        _ = registry.version
    with pytest.raises(RuntimeError, match="closed"):
        registry.register(tool("alpha"))


def test_schema_router_can_plan_and_execute_with_reopened_sqlite_registry(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"

    with SQLiteRegistry(path) as registry:
        registry.register(tool("weather"))

    with SQLiteRegistry(path) as reopened:
        router = SchemaRouter(registry=reopened)
        router.executor.bind(
            "weather",
            lambda endpoint, arguments: {"value": f"result:{arguments['id']}"},
        )

        result = router.invoke(
            PlanRequest(
                query="weather value",
                arguments={"id": "seoul"},
            )
        )

        assert result[0].tool == "weather"
        assert result[0].data == {"value": "result:seoul"}



def test_sqlite_registry_revalidates_nested_mutation_before_transaction(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    mutated = tool("mutated")
    mutated.endpoints[0].parameters.append(
        ParameterSpec(name="id", required=False)
    )

    with SQLiteRegistry(path) as registry:
        with pytest.raises(RegistrationError, match="not a valid ToolSpec"):
            registry.register(mutated)

        assert registry.version == 0
        assert registry.keys() == ()



def test_sqlite_registry_migrates_legacy_execution_metadata_on_read(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    registry = SQLiteRegistry(path)
    registry.close()

    legacy_document = {
        "name": "legacy_remote",
        "endpoints": [
            {
                "name": "run",
                "read_only": None,
                "metadata": {
                    "request_body_mode": "root_schema",
                    "request_body_required": True,
                },
            }
        ],
        "metadata": {
            "adapter": "openapi",
            "source_url": "https://docs.example.test/openapi.json",
            "approved_base_url": "https://api.example.test/v1",
            "execution_bound": True,
        },
    }

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO schemarouter_registry_tools (key, position, document)
            VALUES (?, ?, ?)
            """,
            (
                "legacy_remote",
                0,
                json.dumps(legacy_document),
            ),
        )
        connection.execute(
            "UPDATE schemarouter_registry_meta SET value = 1 WHERE key = 'version'"
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteRegistry(path) as reopened:
        tool = reopened.get("legacy_remote")

    assert tool.remote is True
    assert tool.execution_metadata["adapter"] == "openapi"
    assert "source_url" not in tool.execution_metadata
    assert tool.metadata["source_url"] == "https://docs.example.test/openapi.json"
    assert tool.execution_metadata["approved_base_url"] == "https://api.example.test/v1"
    assert tool.execution_metadata["execution_bound"] is True
    assert tool.endpoints[0].execution_metadata["request_body_mode"] == "root_schema"
    assert tool.endpoints[0].execution_metadata["request_body_required"] is True

import pytest

from schemarouter import EndpointSpec, InMemoryRegistry, ParameterSpec, RegistrationError, ToolSpec


def test_registry_rejects_collisions_without_replace() -> None:
    reg = InMemoryRegistry()
    tool = ToolSpec(name="demo", endpoints=[EndpointSpec(name="run")])
    reg.register(tool)
    with pytest.raises(RegistrationError):
        reg.register(tool)


def test_namespace_disambiguates_tools() -> None:
    reg = InMemoryRegistry()
    reg.register(ToolSpec(name="search", namespace="a", endpoints=[EndpointSpec(name="run")]))
    reg.register(ToolSpec(name="search", namespace="b", endpoints=[EndpointSpec(name="run")]))
    assert reg.keys() == ("a.search", "b.search")


def test_schema_router_accepts_structural_registry_implementation() -> None:
    from schemarouter import SchemaRouter

    class ProxyRegistry:
        def __init__(self) -> None:
            self.inner = InMemoryRegistry()

        @property
        def version(self) -> int:
            return self.inner.version

        def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
            return self.inner.register(tool, replace=replace)

        def get(self, key: str) -> ToolSpec:
            return self.inner.get(key)

        def tools(self) -> tuple[ToolSpec, ...]:
            return self.inner.tools()

        def keys(self) -> tuple[str, ...]:
            return self.inner.keys()

        def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
            return self.inner.endpoint(tool_key, endpoint_name)

    registry = ProxyRegistry()
    router = SchemaRouter(registry=registry)
    router.add_tool(
        ToolSpec(
            name="custom",
            endpoints=[EndpointSpec(name="ping")],
        )
    )

    assert router.registry is registry
    assert registry.keys() == ("custom",)


def test_registry_snapshots_input_on_registration() -> None:
    reg = InMemoryRegistry()
    original = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="run")],
    )
    reg.register(original)
    version = reg.version

    original.name = "mutated"
    original.endpoints[0].name = "changed"

    assert reg.version == version
    assert reg.keys() == ("demo",)
    assert reg.get("demo").name == "demo"
    assert reg.endpoint("demo", "run").name == "run"


def test_registry_reads_are_detached_snapshots() -> None:
    reg = InMemoryRegistry()
    reg.register(
        ToolSpec(
            name="demo",
            endpoints=[EndpointSpec(name="run")],
        )
    )
    version = reg.version

    snapshot = reg.get("demo")
    snapshot.name = "mutated"
    snapshot.endpoints[0].name = "changed"
    snapshot.metadata["unexpected"] = True

    assert reg.version == version
    assert reg.keys() == ("demo",)
    assert reg.get("demo").name == "demo"
    assert reg.endpoint("demo", "run").name == "run"
    assert "unexpected" not in reg.get("demo").metadata


def test_registry_unregisters_and_versions_changes() -> None:
    reg = InMemoryRegistry()
    reg.register(ToolSpec(name="demo", endpoints=[EndpointSpec(name="run")]))
    version = reg.version

    reg.unregister("demo")

    assert reg.version == version + 1
    assert reg.keys() == ()
    with pytest.raises(KeyError):
        reg.get("demo")
    with pytest.raises(KeyError):
        reg.unregister("demo")


def test_registry_update_many_is_atomic_for_duplicate_batch_keys() -> None:
    reg = InMemoryRegistry()
    duplicate = ToolSpec(name="demo", endpoints=[EndpointSpec(name="run")])

    with pytest.raises(RegistrationError, match="duplicate tool keys"):
        reg.update_many([duplicate, duplicate.model_copy(deep=True)])

    assert reg.version == 0
    assert reg.keys() == ()


def test_registry_update_many_rejects_existing_collisions_without_replace() -> None:
    reg = InMemoryRegistry()
    original = ToolSpec(name="demo", endpoints=[EndpointSpec(name="run")])
    reg.register(original)
    version = reg.version

    with pytest.raises(RegistrationError, match="tools already registered"):
        reg.update_many([original.model_copy(deep=True)])

    assert reg.version == version
    assert reg.keys() == ("demo",)


def test_registry_update_many_replaces_in_one_version_step() -> None:
    reg = InMemoryRegistry()
    reg.register(ToolSpec(name="demo", endpoints=[EndpointSpec(name="old")]))
    version = reg.version

    reg.update_many(
        [
            ToolSpec(name="demo", endpoints=[EndpointSpec(name="new")]),
            ToolSpec(name="second", endpoints=[EndpointSpec(name="run")]),
        ],
        replace=True,
    )

    assert reg.version == version + 1
    assert reg.keys() == ("demo", "second")
    assert reg.endpoint("demo", "new").name == "new"


def test_registry_empty_update_many_is_a_noop() -> None:
    reg = InMemoryRegistry()
    version = reg.version

    reg.update_many([])

    assert reg.version == version



def test_descriptive_metadata_does_not_change_execution_fingerprints() -> None:
    old = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                metadata={"note": "old"},
            )
        ],
        metadata={"catalog_note": "old"},
    )
    new = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                metadata={"note": "new"},
            )
        ],
        metadata={"catalog_note": "new"},
    )

    assert old.endpoints[0].fingerprint == new.endpoints[0].fingerprint
    assert old.fingerprint == new.fingerprint


def test_execution_metadata_changes_execution_fingerprints() -> None:
    old = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                execution_metadata={"mode": "search"},
            )
        ],
        execution_metadata={"approved_base_url": "https://a.example/api"},
    )
    new = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                execution_metadata={"mode": "get"},
            )
        ],
        execution_metadata={"approved_base_url": "https://b.example/api"},
    )

    assert old.endpoints[0].fingerprint != new.endpoints[0].fingerprint
    assert old.fingerprint != new.fingerprint



def test_registry_revalidates_nested_endpoint_mutation_before_write() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="mutated",
        endpoints=[EndpointSpec(name="run")],
    )
    tool.endpoints.append(EndpointSpec(name="run"))

    with pytest.raises(RegistrationError, match="not a valid ToolSpec"):
        registry.register(tool)

    assert registry.keys() == ()
    assert registry.version == 0


def test_registry_revalidates_nested_parameter_mutation_in_batch() -> None:
    registry = InMemoryRegistry()
    endpoint = EndpointSpec(
        name="run",
        parameters=[ParameterSpec(name="value")],
    )
    tool = ToolSpec(name="mutated", endpoints=[endpoint])
    tool.endpoints[0].parameters.append(ParameterSpec(name="value"))

    with pytest.raises(RegistrationError, match="not a valid ToolSpec"):
        registry.update_many([tool])

    assert registry.keys() == ()
    assert registry.version == 0



def test_execution_metadata_requires_canonical_json_safe_values() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        ToolSpec(
            name="invalid_execution_metadata",
            endpoints=[EndpointSpec(name="run")],
            execution_metadata={"opaque": object()},
        )

    with pytest.raises(ValueError, match="finite JSON numbers"):
        EndpointSpec(
            name="run",
            execution_metadata={"weight": float("nan")},
        )


def test_descriptive_metadata_can_remain_non_json_for_in_memory_use() -> None:
    opaque = object()
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="descriptive",
            endpoints=[EndpointSpec(name="run")],
            metadata={"opaque": opaque},
        )
    )

    assert registry.get("descriptive").metadata["opaque"] is not None



def test_generic_descriptive_metadata_is_not_legacy_migrated_by_key_name_alone() -> None:
    endpoint = EndpointSpec(
        name="run",
        metadata={"mode": "documentation-only"},
    )
    tool = ToolSpec(
        name="local",
        endpoints=[endpoint],
        metadata={"source_url": "https://docs.example.test/local"},
    )

    assert endpoint.execution_metadata == {}
    assert tool.execution_metadata == {}
    assert tool.remote is False


def test_legacy_optimade_tool_metadata_migrates_adapter_specific_identity() -> None:
    tool = ToolSpec(
        name="materials",
        endpoints=[
            EndpointSpec(
                name="search",
                metadata={
                    "entry_type": "structures",
                    "mode": "search",
                    "field_projection": "response_fields",
                },
            )
        ],
        metadata={
            "adapter": "optimade",
            "api_version": "1.3.0",
            "versioned_base_url": "https://optimade.example/v1",
            "source_url": "descriptive-only-for-this-adapter",
        },
    )

    assert tool.execution_metadata == {
        "adapter": "optimade",
        "api_version": "1.3.0",
        "versioned_base_url": "https://optimade.example/v1",
    }
    assert tool.endpoints[0].execution_metadata == {
        "entry_type": "structures",
        "field_projection": "response_fields",
        "mode": "search",
    }



@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "", "provider must be non-empty"),
        ("provider", "   ", "provider must be non-empty"),
        ("access_mode", "", "access_mode must be non-empty"),
        ("access_mode", "   ", "access_mode must be non-empty"),
    ],
)
def test_tool_rejects_empty_provider_access_identity(
    field: str,
    value: str,
    message: str,
) -> None:
    kwargs = {
        "name": "demo",
        "endpoints": [EndpointSpec(name="read", read_only=True)],
        field: value,
    }

    with pytest.raises(ValueError, match=message):
        ToolSpec(**kwargs)



def test_inmemory_compare_and_swap_replaces_only_the_snapshot_it_validated() -> None:
    reg = InMemoryRegistry()
    original = ToolSpec(
        name="demo",
        description="original",
        endpoints=[EndpointSpec(name="run")],
    )
    reg.register(original)
    expected_version = reg.version
    expected = reg.get("demo").fingerprint
    version = reg.version

    amended = original.model_copy(update={"description": "amended"})
    assert reg.replace_if_fingerprint(
        amended,
        expected_fingerprint=expected,
        expected_version=expected_version,
    ) == "demo"
    assert reg.version == version + 1
    assert reg.get("demo").description == "amended"


def test_inmemory_compare_and_swap_refuses_a_lost_update_without_version_bump() -> None:
    reg = InMemoryRegistry()
    original = ToolSpec(
        name="demo",
        description="original",
        endpoints=[EndpointSpec(name="run")],
    )
    reg.register(original)
    stale_version = reg.version
    stale_fingerprint = reg.get("demo").fingerprint

    interloper = original.model_copy(update={"description": "newer writer"})
    reg.register(interloper, replace=True)
    version_before_failed_cas = reg.version

    stale_amendment = original.model_copy(update={"description": "stale amendment"})
    with pytest.raises(RegistrationError, match="changed concurrently"):
        reg.replace_if_fingerprint(
            stale_amendment,
            expected_fingerprint=stale_fingerprint,
            expected_version=stale_version,
        )

    assert reg.version == version_before_failed_cas
    assert reg.get("demo").description == "newer writer"


def test_base_registry_protocol_does_not_require_compare_and_swap() -> None:
    """Existing structural registries stay valid for ordinary planning/registration."""

    from schemarouter import SchemaRouter

    class LegacyRegistry:
        def __init__(self) -> None:
            self.inner = InMemoryRegistry()

        @property
        def version(self) -> int:
            return self.inner.version

        def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
            return self.inner.register(tool, replace=replace)

        def get(self, key: str) -> ToolSpec:
            return self.inner.get(key)

        def tools(self) -> tuple[ToolSpec, ...]:
            return self.inner.tools()

        def keys(self) -> tuple[str, ...]:
            return self.inner.keys()

        def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
            return self.inner.endpoint(tool_key, endpoint_name)

    registry = LegacyRegistry()
    router = SchemaRouter(registry=registry)
    assert router.add_tool(
        ToolSpec(name="legacy", endpoints=[EndpointSpec(name="run")])
    ) == "legacy"



def test_inmemory_cas_detects_metadata_only_concurrent_write_even_when_fingerprint_matches(
) -> None:
    reg = InMemoryRegistry()
    original = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="run")],
        metadata={"note": "old"},
    )
    reg.register(original)
    expected_version = reg.version
    expected_fingerprint = reg.get("demo").fingerprint

    interloper = reg.get("demo")
    interloper.metadata["note"] = "concurrent writer"
    assert interloper.fingerprint == expected_fingerprint
    reg.register(interloper, replace=True)

    amendment = original.model_copy(deep=True)
    amendment.endpoints[0].description = "trusted annotation"
    with pytest.raises(RegistrationError, match="registry changed concurrently"):
        reg.replace_if_fingerprint(
            amendment,
            expected_fingerprint=expected_fingerprint,
            expected_version=expected_version,
        )

    assert reg.get("demo").metadata["note"] == "concurrent writer"


def test_inmemory_registry_batch_cas_is_atomic() -> None:
    reg = InMemoryRegistry()
    expected_version = reg.version
    tools = (
        ToolSpec(name="batch_a", endpoints=[EndpointSpec(name="run")]),
        ToolSpec(name="batch_b", endpoints=[EndpointSpec(name="run")]),
    )

    keys = reg.update_many_if_version(tools, expected_version=expected_version)

    assert keys == ("batch_a", "batch_b")
    assert reg.keys() == keys
    assert reg.version == expected_version + 1


def test_inmemory_registry_batch_cas_rejects_stale_version_without_partial_write() -> None:
    reg = InMemoryRegistry()
    expected_version = reg.version
    reg.register(ToolSpec(name="concurrent", endpoints=[EndpointSpec(name="run")]))
    tools = (
        ToolSpec(name="batch_a", endpoints=[EndpointSpec(name="run")]),
        ToolSpec(name="batch_b", endpoints=[EndpointSpec(name="run")]),
    )

    with pytest.raises(RegistrationError, match="registry changed concurrently"):
        reg.update_many_if_version(tools, expected_version=expected_version)

    assert reg.keys() == ("concurrent",)

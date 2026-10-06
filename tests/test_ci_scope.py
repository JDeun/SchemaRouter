from scripts.ci_scope import classify_paths


def test_ci_scope_core_runtime_change_is_not_full_fanout() -> None:
    scopes = classify_paths(["src/schemarouter/runtime.py"])

    assert scopes["package"] is True
    assert scopes["runtime"] is True
    assert scopes["full"] is False
    assert scopes["pydanticai"] is False
    assert scopes["docs"] is False


def test_ci_scope_native_adapter_targets_native_qualification() -> None:
    scopes = classify_paths(["src/schemarouter/adapters/vector_native.py"])

    assert scopes["native"] is True
    assert scopes["package"] is True
    assert scopes["database"] is False


def test_ci_scope_docs_only_does_not_request_package_qualification() -> None:
    scopes = classify_paths(["docs/guides/runtime.md"])

    assert scopes["docs"] is True
    assert scopes["package"] is False
    assert scopes["runtime"] is False


def test_ci_scope_dependency_change_expands_optional_integration_surface() -> None:
    scopes = classify_paths(["pyproject.toml"])

    assert scopes["deps"] is True
    assert scopes["package"] is True
    assert scopes["langchain"] is True
    assert scopes["llamaindex"] is True
    assert scopes["mcp"] is True
    assert scopes["database"] is True


def test_ci_scope_ci_definition_change_requests_full_qualification() -> None:
    scopes = classify_paths([".github/workflows/ci.yml"])

    assert all(scopes.values())

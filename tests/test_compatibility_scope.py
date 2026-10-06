from scripts.compatibility_scope import classify_paths


def test_vector_change_only_selects_vector_and_matrix() -> None:
    scopes = classify_paths(["src/schemarouter/adapters/vector_native.py"])

    assert scopes["vector"] is True
    assert scopes["matrix"] is True
    assert scopes["record"] is False
    assert scopes["graph"] is False
    assert scopes["providers"] is False


def test_provider_profile_change_selects_provider_and_matrix() -> None:
    scopes = classify_paths(["src/schemarouter/provider_profiles.py"])

    assert scopes["providers"] is True
    assert scopes["matrix"] is True
    assert scopes["vector"] is False


def test_openapi_change_does_not_start_database_backends() -> None:
    scopes = classify_paths(["src/schemarouter/adapters/openapi.py"])

    assert scopes["openapi"] is True
    assert scopes["matrix"] is True
    assert scopes["vector"] is False
    assert scopes["record"] is False
    assert scopes["graph"] is False


def test_compatibility_workflow_change_forces_full_surface() -> None:
    scopes = classify_paths([".github/workflows/compatibility.yml"])

    assert all(scopes.values())

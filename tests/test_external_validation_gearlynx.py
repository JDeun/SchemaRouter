from scripts.external_validation_gearlynx import CASES, evaluate, load_catalog, native_search


def test_gearlynx_fixture_is_pinned_and_nontrivial():
    fixture = load_catalog()
    assert fixture["upstream"]["commit"] == "58c0fa0fa2abe1b0b7da885640b32bce4ff3677f"
    assert fixture["tool_count"] == len(fixture["tools"]) == 82
    assert sum(tool["direct"] for tool in fixture["tools"]) == 12


def test_native_search_matches_frozen_examples():
    tools = load_catalog()["tools"]
    assert "get_suzy_registers" in native_search("suzy registers", tools)
    assert "get_uart_status" in native_search("uart status", tools)
    assert native_search("weather forecast", tools) == []


def test_evaluation_preserves_execution_boundary():
    result = evaluate()
    assert len(result["cases"]) == len(CASES)
    assert result["boundary"]["execution_through_schemarouter"] is False
    assert result["catalog"]["tool_count"] == 82
    assert result["field_recall"]["status"] == "not_reported"
    assert all("native_schema_source_bytes" in row for row in result["cases"])
    assert all("schemarouter_schema_source_bytes" in row for row in result["cases"])
    assert "mean_schema_source_bytes" in result["native_summary"]
    assert "mean_schema_source_bytes" in result["schemarouter_summary"]

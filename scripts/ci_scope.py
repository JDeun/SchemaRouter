"""Classify pull-request changed paths into CI qualification scopes."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from collections.abc import Iterable

_SCOPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "full": (
        ".github/workflows/ci.yml",
        "scripts/ci_scope.py",
        "tests/test_ci_scope.py",
    ),
    "native": (
        "src/schemarouter/adapters/*_native.py",
        "src/schemarouter/adapters/graph_store.py",
        "src/schemarouter/adapters/vector_store.py",
        "src/schemarouter/adapters/record_store.py",
        "tests/test_*native*.py",
        "tests/test_graph_store_adapter.py",
        "tests/test_vector_store_adapter.py",
        "tests/test_record_store_adapter.py",
    ),
    "deps": (
        "pyproject.toml",
        "requirements*.txt",
        "**/requirements*.txt",
    ),
    "package": (
        "pyproject.toml",
        "src/schemarouter/**",
        "scripts/consumer_acceptance.py",
        "scripts/quickstart_provider_contract_smoke.py",
        "examples/**",
    ),
    "runtime": (
        "src/schemarouter/runtime.py",
        "src/schemarouter/executor.py",
        "src/schemarouter/cli.py",
        "src/schemarouter/__init__.py",
        "tests/test_runtime*.py",
        "tests/test_executor.py",
        "tests/test_cli.py",
        "tests/test_public_api.py",
    ),
    "adapter_plugin": (
        "src/schemarouter/adapters/plugins.py",
        "src/schemarouter/adapters/__init__.py",
        "examples/adapter_plugin_demo/**",
        "scripts/downstream_adapter_plugin_smoke.py",
    ),
    "pydanticai": (
        "examples/external_validation/pydanticai-tool-search/**",
        "scripts/external_validation_pydanticai.py",
    ),
    "openai_agents": (
        "examples/external_validation/openai_agents_mcp_filter/**",
        "scripts/external_validation_openai_agents.py",
    ),
    "mcp_agent": (
        "examples/external_validation/mcp_agent_catalog/**",
        "scripts/external_validation_mcp_agent.py",
    ),
    "langchain": (
        "src/schemarouter/integrations/langchain.py",
        "src/schemarouter/integrations/langgraph.py",
        "tests/test_langchain_integration.py",
        "tests/test_langgraph_integration.py",
        "examples/langchain_quickstart.py",
        "examples/langgraph_quickstart.py",
    ),
    "llamaindex": (
        "src/schemarouter/integrations/llamaindex.py",
        "tests/test_llamaindex_integration.py",
        "examples/llamaindex_quickstart.py",
    ),
    "jev": (
        "src/schemarouter/integrations/jev.py",
        "tests/test_jev_integration.py",
    ),
    "laya": (
        "src/schemarouter/integrations/laya.py",
        "tests/test_laya_integration.py",
    ),
    "otel": (
        "src/schemarouter/integrations/opentelemetry.py",
        "tests/test_opentelemetry_integration.py",
    ),
    "mcp": (
        "src/schemarouter/adapters/mcp.py",
        "tests/test_mcp_integration.py",
        "examples/mcp_stdio_quickstart.py",
    ),
    "database": (
        "src/schemarouter/adapters/sqlite_database.py",
        "src/schemarouter/adapters/sqlalchemy_database.py",
        "tests/test_sqlite_database_adapter.py",
        "tests/test_sqlalchemy_database_adapter.py",
        "examples/database_quickstart.py",
        "scripts/installed_database_smoke.py",
    ),
    "docs": (
        "docs/**",
        "docs_ko/**",
        "mkdocs*.yml",
        "README.md",
        "README.ko.md",
    ),
}


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    normalized = tuple(path.strip().replace("\\", "/") for path in paths if path.strip())
    result = {
        scope: any(_matches(path, pattern) for path in normalized for pattern in patterns)
        for scope, patterns in _SCOPE_PATTERNS.items()
    }

    if result["full"]:
        for scope in result:
            result[scope] = True
        return result

    # Dependency metadata can change the behavior of every optional integration.
    if result["deps"]:
        for scope in (
            "package",
            "adapter_plugin",
            "pydanticai",
            "openai_agents",
            "mcp_agent",
            "langchain",
            "llamaindex",
            "jev",
            "laya",
            "otel",
            "mcp",
            "database",
        ):
            result[scope] = True

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="emit key=true|false lines suitable for GITHUB_OUTPUT",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    paths = args.paths or [line.rstrip("\n") for line in sys.stdin]
    result = classify_paths(paths)
    if args.github_output:
        for key, enabled in result.items():
            print(f"{key}={'true' if enabled else 'false'}")
    else:
        enabled = [key for key, value in result.items() if value]
        print(" ".join(enabled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

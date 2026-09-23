# Installation

SchemaRouter requires Python 3.10 or newer.

## Published release

The current public release is `0.5.0`:

```bash
pip install schemarouter
```

The release includes the structured-source core, bounded decision backends, OpenAPI/OPTIMADE/MCP,
LangChain/LlamaIndex bridges, authenticated MCP transports, approval/budgets, OpenTelemetry, and
the explicit adapter-plugin contract.

## Development checkout

For local development and tests:

```bash
git clone https://github.com/JDeun/SchemaRouter.git
cd SchemaRouter
pip install -e ".[dev]"
```

## Optional extras

Install only the integrations you use.

=== "MCP"

    ```bash
    pip install "schemarouter[mcp]"
    ```

=== "LangChain"

    ```bash
    pip install "schemarouter[langchain]"
    ```

=== "LlamaIndex"

    ```bash
    pip install "schemarouter[llamaindex]"
    ```

=== "Jev / TypeSafe"

    ```bash
    pip install "schemarouter[jev]"
    ```

=== "Laya (0.6 development)"

    The current public `0.5.0` package does not contain the Laya extra yet.

    ```bash
    pip install -e ".[laya]"
    ```

    The packaged `schemarouter[laya]` extra will become available in the first release that
    includes the 0.6 development work.

=== "OpenTelemetry"

    ```bash
    pip install "schemarouter[otel]"
    ```

=== "Documentation"

    ```bash
    pip install -e ".[docs]"
    mkdocs serve
    ```

## Verify the installation

```bash
python -c "import schemarouter; print(schemarouter.__version__)"
```

The published release tag and package metadata identify `0.5.0` as the current non-prerelease
release. Development snapshots use PEP 440 `.dev0` versions so source checkouts remain
distinguishable from released artifacts.

## Release verification

Package metadata, wheel/sdist build, clean-wheel installation, integration contracts, and strict
documentation builds are verified in CI. External-service smokes are kept separate from deterministic
pull-request gates.

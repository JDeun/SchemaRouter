# Installation

SchemaRouter requires Python 3.10 or newer.

## Published alpha

The current pre-release is `0.3.0a1`:

```bash
pip install --pre schemarouter
```

The alpha includes the structured-source core, bounded decision backends, OpenAPI/OPTIMADE/MCP,
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
    pip install --pre "schemarouter[mcp]"
    ```

=== "LangChain"

    ```bash
    pip install --pre "schemarouter[langchain]"
    ```

=== "LlamaIndex"

    ```bash
    pip install --pre "schemarouter[llamaindex]"
    ```

=== "Jev / TypeSafe"

    ```bash
    pip install --pre "schemarouter[jev]"
    ```

=== "OpenTelemetry"

    ```bash
    pip install --pre "schemarouter[otel]"
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

The release tag and package metadata identify this artifact as `0.3.0a1`. Development branches
use PEP 440 development versions so source checkouts remain distinguishable from released artifacts.

## Release verification

Package metadata, wheel/sdist build, clean-wheel installation, integration contracts, and strict
documentation builds are verified in CI. External-service smokes are kept separate from deterministic
pull-request gates.

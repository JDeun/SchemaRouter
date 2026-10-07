# Installation

SchemaRouter requires Python 3.10 or newer.

## Published release

The current public release is `0.17.0`:

```bash
pip install schemarouter
```

The release keeps the 0.12 stable-core retrieval/execution boundary and adds the 0.14 operational
surface: source probing, startup rebinding, storage migrations, explicit schema-drift review,
unified shutdown, the Capability Explorer, bilingual documentation, and broader installed-package
ecosystem validation. See the [0.14.0 release notes](../releases/0.14.0.md).

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

=== "Laya"

    ```bash
    pip install "schemarouter[laya]"
    ```

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

The published release tag and package metadata identify `0.17.0` as the current non-prerelease
release. Development snapshots use PEP 440 `.dev0` versions so source checkouts remain
distinguishable from released artifacts.

## Release verification

Package metadata, wheel/sdist build, clean-wheel installation, integration contracts, and strict
documentation builds are verified in CI. External-service smokes are kept separate from deterministic
pull-request gates.

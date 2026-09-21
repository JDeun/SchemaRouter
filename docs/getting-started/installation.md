# Installation

SchemaRouter requires Python 3.10 or newer.

## Published alpha

The published pre-release is `0.2.0a1`:

```bash
pip install --pre schemarouter
```

The published alpha contains the v0.2 core, OpenAPI/OPTIMADE/MCP support, and the LangChain bridge.

## Current main

Current `main` contains unreleased next-release work, including bounded decision backends,
LlamaIndex integration, and the Jev / TypeSafe provider. Install those features from source:

```bash
git clone https://github.com/JDeun/SchemaRouter.git
cd SchemaRouter
pip install -e .
```

For local development and tests:

```bash
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

=== "LlamaIndex (current main)"

    ```bash
    pip install -e ".[llamaindex]"
    ```

=== "Jev / TypeSafe (current main)"

    ```bash
    pip install -e ".[jev]"
    ```

=== "Documentation"

    ```bash
    pip install -e ".[docs]"
    mkdocs serve
    ```

After the next package release, the LlamaIndex and Jev extras will use the same normal package-extra
form (`schemarouter[llamaindex]` and `schemarouter[jev]`).

## Verify the installation

```bash
python -c "import schemarouter; print(schemarouter.__version__)"
```

The repository `main` branch identifies itself as `0.3.0.dev0`, while the published alpha
remains `0.2.0a1`. This keeps source checkouts distinguishable from released artifacts through
normal package metadata.

## Release verification

Package metadata, wheel/sdist build, clean-wheel installation, integration contracts, and strict
documentation builds are verified in CI. External-service smokes are kept separate from deterministic
pull-request gates.

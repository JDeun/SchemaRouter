# Installation

SchemaRouter requires Python 3.10 or newer.

## Current pre-release

The project is currently developed from source. Clone the repository and install it in editable mode:

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
    pip install -e ".[mcp]"
    ```

=== "LangChain"

    ```bash
    pip install -e ".[langchain]"
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

The current pre-release version is `0.2.0a1`.

## Package release

The package metadata, wheel build, source distribution, and clean-wheel installation are verified in
CI. After `0.2.0a1` is published to the package index, the standard installation path will be:

```bash
pip install schemarouter
```

Do not rely on that command until a release is visible on the package index.

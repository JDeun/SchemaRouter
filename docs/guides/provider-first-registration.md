# Provider-first registration

Most users know the **provider they want**, not every protocol or SDK that provider exposes.

SchemaRouter keeps its protocol-neutral ingestion architecture internally, but known providers can be registered from a provider identity:

```python
from schemarouter import SchemaRouter

router = SchemaRouter()
result = await router.add_provider("materials-project")
```

The built-in profile resolves the provider into its known access methods and only registers methods that are safe and usable in the current process. Missing credentials or optional dependencies are reported rather than guessed or installed.

## Inspect before registering

Provider resolution is local and does not make network calls:

```python
resolution = router.resolve_provider("materials-project")

for method in resolution.methods:
    print(method.method_id, method.status, method.credential_names)
```

A typical environment may report:

```text
optimade    available
openapi     available    credential: X-API-KEY
python-sdk  dependency_missing
```

Credential requirements are declarations only. Secret values are never stored in provider profiles, ToolSpec documents, snapshots, or inspection output.

## Built-in acceptance providers

The built-in acceptance profiles deliberately cover different access shapes:

- **Materials Project** — public OPTIMADE, authenticated OpenAPI, and optional `mp-api` SDK.
- **Crossref** — public declarative HTTP/JSON REST access.
- **Tavily** — authenticated declarative HTTP/JSON search plus an optional Python SDK path.
- **APIs.guru** — public OpenAPI discovery and read-only metrics execution.
- **Countries GraphQL API** — public GraphQL introspection and read-only country query execution.
- **OData.org V4 reference service** — public OData metadata discovery and read-only query execution.

For authenticated methods, supply trusted process-local headers:

```python
result = await router.add_provider(
    "tavily",
    methods={"rest"},
    trusted_headers_by_method={
        "rest": {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    },
)
```

SchemaRouter does not install SDKs automatically. An installed SDK method still requires an explicit trusted binding unless a provider plugin supplies one.

## Multiple access methods remain distinct

Provider-first registration is a convenience layer over the existing adapters:

```text
provider identity
    |
    v
ProviderProfile
    |
    +-- OpenAPI
    +-- OPTIMADE
    +-- HTTP/JSON
    +-- Python / plugin binding
    |
    v
existing ToolSpec / EndpointSpec / FieldSpec pipeline
```

All methods keep a shared `provider` identity and a distinct `access_mode`. Sharing a provider ID does **not** make two methods interchangeable. Existing semantic, datatype, unit, qualifier, health, policy, and fallback rules still apply.

## Extending the catalog

Applications can register a local `ProviderProfile`, and installed packages can expose provider profiles through the `schemarouter.providers` entry-point group. Plugin loading is explicit and allowlisted because importing a Python entry point executes trusted local code.

## Method support

Provider profiles can target every URL-backed adapter in the default registry. The provider-first layer forwards the declared method into the existing adapter instead of implementing protocol-specific registration logic.

| Profile method kind | Provider-first behavior |
| --- | --- |
| `openapi` | automatic URL registration |
| `optimade` | automatic URL registration |
| `graphql` | automatic URL registration |
| `odata` | automatic URL registration |
| `openrpc` | automatic URL registration |
| `mcp` | automatic URL registration for URL-backed MCP transports |
| `http_json` | automatic registration from an explicitly trusted declarative `ToolSpec` |
| `python` / SDK | explicit trusted binding required; package presence alone never grants execution authority |

Caller-owned transports, Python clients, and framework objects remain explicit trust boundaries. Applications can still describe them in a provider profile, but core SchemaRouter does not infer executable authority from an installed package or importable object.

Provider profiles are not an execution planner. They describe how a named provider can be ingested; routing and execution continue through the normal SchemaRouter contracts.

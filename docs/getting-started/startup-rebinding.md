# Startup rebinding for persisted registries

`SQLiteRegistry` persists capability contracts, not live execution authority. Credentials,
HTTP clients, SDK objects, subprocess handles, MCP factories, and other runtime state are
intentionally absent from the database.

After a process restart, reopen the registry and reconcile trusted bindings explicitly:

```python
from schemarouter import SchemaRouter, SQLiteRegistry, TrustedBindingConfig

registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)

def resolve(tool):
    if tool.key == "materials":
        return TrustedBindingConfig(
            trusted_headers={"Authorization": "Bearer ..."},
        )
    if tool.key == "internal_sdk":
        return TrustedBindingConfig(invoker=my_process_local_invoker)
    return None

report = router.rehydrate_bindings(resolve, strict=True)
assert not report.unready
```

The resolver receives a detached ToolSpec snapshot. SchemaRouter never writes credentials or live
objects back into registry state.

## Built-in reconstruction

SchemaRouter can rebuild trusted invokers from persisted non-secret provenance for:

- OpenAPI, using a persisted approved base URL or an explicit trusted `base_url`;
- GraphQL, using the approved endpoint/source URL;
- OData, using the approved service URL;
- OpenRPC, when an approved base URL exists or the application supplies one;
- OPTIMADE, using the persisted versioned API base;
- declarative HTTP/JSON tools, using the approved base URL;
- Streamable HTTP MCP, using the persisted source URL plus any process-local trusted headers.

Some execution authority cannot be serialized safely and must be supplied again:

- MCP stdio/custom/in-process transports require a caller-owned bound factory and the matching
  persisted transport fingerprint;
- Python capabilities require the original callable;
- LangChain and LlamaIndex capabilities require the original framework tool object;
- private SDK/custom adapters require an explicit caller-owned invoker unless they provide another
  trusted local binding layer.

## Reconciliation states

Each item is reported as one of:

- `ready`: an invoker is bound to the exact current ToolSpec fingerprint;
- `intentionally_unbound`: trusted local configuration explicitly disabled execution;
- `missing_trusted_config`: the persisted contract is valid but required live authority was not
  supplied;
- `incompatible`: the supplied live object, transport fingerprint, or concurrent contract does
  not match the persisted capability;
- `failed`: trusted binding construction failed for another reason.

Set `strict=True` to fail startup when required capabilities are not `ready`. When
`required_tools` is omitted, strict mode treats every persisted capability as required.

Strict failures raise `BindingReconciliationError` (a `RegistrationError` subclass). Its
`.report` property retains the same credential-free reconciliation report so startup logging and
operator diagnostics do not need to reconstruct or expose the trusted resolver configuration.

## Security boundary

Rebinding does **not** re-ingest or replace ToolSpecs. The registry fingerprint is read immediately
before binding and passed to the executor as the expected contract fingerprint. If another writer
changes the contract before the invoker is stored, binding fails closed.

Persisted execution URLs are reused only where they already represent an approved execution
location. Schema-document suggestions that required explicit approval remain unbound until the
application supplies a trusted base URL.

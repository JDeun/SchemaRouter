# Compatibility testing

SchemaRouter separates deterministic release gates from external-service smoke tests.

## Supported compatibility matrix

The table below distinguishes the **declared dependency range** from what CI proves on every pull
request. CI installs the currently resolved package versions inside each declared range; it does not
claim that every historical version inside the range is exhaustively tested.

| Surface | Declared support | Pull-request gate | Notes |
| --- | --- | --- | --- |
| Python | 3.10, 3.11, 3.12 | Full core suite on all three versions | Package metadata requires Python >=3.10 |
| LangChain | `langchain-core>=1.6,<2` | Dedicated contract tests + runnable example on Python 3.12 | Optional `schemarouter[langchain]` extra |
| LlamaIndex | `llama-index-core>=0.14,<1` | Dedicated contract tests + runnable example on Python 3.12 | Optional `schemarouter[llamaindex]` extra |
| MCP | `mcp>=2,<3` | Real Streamable HTTP integration against a local server | Optional `schemarouter[mcp]` extra |
| OpenAPI | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OpenAPI SDK dependency |
| OPTIMADE | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OPTIMADE client dependency |

Before widening an upper bound or lowering a minimum supported version, the relevant integration
tests must pass against that target and the change must be documented in release notes.

## Required CI

Every pull request runs:

- Python 3.10 / 3.11 / 3.12 core tests;
- warnings-as-errors;
- executable core quickstart;
- wheel and sdist build + metadata checks;
- LangChain integration contract tests and `examples/langchain_quickstart.py`;
- LlamaIndex integration contract tests and `examples/llamaindex_quickstart.py`;
- real MCP Streamable HTTP integration using the official SDK and a local HTTP server;
- strict MkDocs build.

These tests are deterministic and are release blockers.

## Integration maintenance policy

Optional ecosystem bridges remain thin adapters around SchemaRouter's existing trust boundary.

- The core package must import and run without LangChain, LlamaIndex, or MCP installed.
- Integration modules use lazy imports and bounded dependency ranges.
- An integration may translate framework tool metadata, but execution must still flow through
  SchemaRouter schema identity, policy, binding checks, and validation.
- If a newly released upstream version breaks compatibility inside a declared range, the range may
  be narrowed temporarily while the bridge is repaired. The change must be documented.
- New upstream major versions are unsupported until dedicated CI coverage is added.
- Public examples are treated as compatibility contracts and must remain executable in CI.

### Package layout decision

For now, the LangChain and LlamaIndex bridges stay inside the main distribution as optional extras:
`schemarouter[langchain]` and `schemarouter[llamaindex]`.

A separate package such as `langchain-schemarouter` should be introduced only if at least one of
these becomes true:

1. the integration needs an independent release cadence;
2. dependency pressure would otherwise widen the core package's maintenance surface materially;
3. upstream maintainers require a dedicated distribution for discoverability or certification;
4. the integration grows beyond a thin translation layer.

This avoids premature package fragmentation while keeping the core dependency graph clean.

## Live OpenAPI smoke

The `Compatibility Smoke` workflow runs weekly and can also be triggered manually. It imports and
executes against the public Swagger Petstore OpenAPI endpoint.

This specifically exercises a common real-world pattern:

- relative OpenAPI `servers` URL;
- query parameter enum;
- read-only remote execution;
- array response;
- nested local `#/components/...` references;
- runtime output validation.

The default source is:

```text
https://petstore3.swagger.io/api/v3/openapi.json
```

Set `SCHEMAROUTER_LIVE_OPENAPI_URL` when running the smoke script locally to use another compatible
service.

External smoke failures are compatibility signals, not pull-request blockers, because third-party
availability is outside SchemaRouter's control.

## Release interpretation

A green required CI proves package and protocol behavior under controlled conditions. A recent green
live smoke provides additional evidence that the OpenAPI adapter remains compatible with a real
public service. Both should be reviewed before a release candidate is promoted.

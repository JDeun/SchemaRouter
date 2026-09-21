# Compatibility testing

SchemaRouter separates deterministic release gates from external-service smoke tests.

## Supported compatibility matrix

The table below distinguishes the **declared dependency range** from what CI proves on every pull
request. CI installs the currently resolved package versions inside each declared range; it does not
claim that every historical version inside the range is exhaustively tested.

| Surface | Declared support | Pull-request gate | Notes |
| --- | --- | --- | --- |
| Python | 3.10, 3.11, 3.12, 3.13, 3.14 | Full core suite on all five versions | Package metadata requires Python >=3.10; Python 3.15 RC is exercised as a non-blocking preview |
| LangChain | `langchain-core>=1.6,<2` | Dedicated contract tests + runnable example on Python 3.12 | Optional `schemarouter[langchain]` extra |
| LlamaIndex | `llama-index-core>=0.14,<1` | Dedicated contract tests + runnable example on Python 3.12 | Optional `schemarouter[llamaindex]` extra |
| Jev / TypeSafe | `typesafe-sdk>=0.7,<1` | Dedicated adversarial contract tests on Python 3.12 | Optional `schemarouter[jev]` extra; no live API call in required CI |
| MCP | `mcp>=2,<3` | Real Streamable HTTP integration against a local server | Optional `schemarouter[mcp]` extra |
| OpenAPI | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OpenAPI SDK dependency |
| OPTIMADE | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OPTIMADE client dependency |

Before widening an upper bound or lowering a minimum supported version, the relevant integration
tests must pass against that target and the change must be documented in release notes.

## Required CI

Every pull request runs:

- Python 3.10 / 3.11 / 3.12 / 3.13 / 3.14 core tests;
- a non-blocking Python 3.15 release-candidate preview job;
- a Windows + Python 3.14 core smoke test;
- warnings-as-errors;
- Pyright static type checking across the packaged surface;
- full-suite branch coverage with an 82% blocking floor and a retained XML artifact;
- a minimum-runtime-dependency job that exercises the declared lower bounds;
- executable core quickstart;
- wheel and sdist build + metadata checks;
- clean-environment installation and quickstart smoke tests from both wheel and sdist;
- LangChain integration contract tests and `examples/langchain_quickstart.py`;
- LlamaIndex integration contract tests and `examples/llamaindex_quickstart.py`;
- Jev adapter adversarial tests with the official SDK installed but no external API dependency;
- real MCP Streamable HTTP integration using the official SDK and a local HTTP server;
- strict MkDocs build.

All jobs above are deterministic release blockers except the explicitly non-blocking Python 3.15
preview. The preview exists to surface upcoming interpreter incompatibilities before Python 3.15
becomes a supported stable release.

## Integration maintenance policy

Optional ecosystem bridges remain thin adapters around SchemaRouter's existing trust boundary.

- The core package must import and run without LangChain, LlamaIndex, Jev/TypeSafe, or MCP
  installed.
- Integration modules use lazy imports and bounded dependency ranges.
- An integration may translate framework/provider metadata, but execution must still flow through
  SchemaRouter schema identity, policy, binding checks, and validation.
- If a newly released upstream version breaks compatibility inside a declared range, the range may
  be narrowed temporarily while the bridge is repaired. The change must be documented.
- New upstream major versions are unsupported until dedicated CI coverage is added.
- Public examples and documented security invariants are compatibility contracts.

### Package layout decision

For now, the LangChain and LlamaIndex bridges stay inside the main distribution as optional extras:
`schemarouter[langchain]` and `schemarouter[llamaindex]`.

A separate package such as `langchain-schemarouter` should be introduced only if at least one of
these becomes true:

1. the integration needs an independent release cadence;
2. dependency pressure would otherwise widen the core package's maintenance surface materially;
3. upstream maintainers require a dedicated distribution for discoverability or certification;
4. the integration grows beyond a thin translation layer.

The Jev provider follows the same principle: it remains an optional `schemarouter[jev]` extra and
does not make TypeSafe a core dependency.

## External compatibility checks

The `Compatibility Smoke` workflow runs weekly and can also be triggered manually for public
OpenAPI/OPTIMADE services.

External-service failures are compatibility signals, not pull-request blockers, because third-party
availability is outside SchemaRouter's control.

Live Jev benchmarking is also intentionally excluded from required CI. Run it explicitly with
`TYPESAFE_API_KEY` using `scripts/benchmark_decision_routing.py --jev`.

## Live OpenAPI smoke

The public OpenAPI smoke imports and executes against Swagger Petstore.

The default source is:

```text
https://petstore3.swagger.io/api/v3/openapi.json
```

Set `SCHEMAROUTER_LIVE_OPENAPI_URL` when running the smoke script locally to use another compatible
service.

## Release interpretation

A green required CI proves package and protocol behavior under controlled conditions. Recent green
external smokes provide additional evidence that remote adapters remain compatible with real public
services. Both should be reviewed before a release candidate is promoted.

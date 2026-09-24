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
| LangGraph | `langgraph>=1.2,<2` | Real `StateGraph` sync/async contract tests + runnable example on Python 3.12 | Optional `schemarouter[langgraph]` extra |
| LlamaIndex | `llama-index-core>=0.14,<1` | Dedicated contract tests + runnable example on Python 3.12 | Optional `schemarouter[llamaindex]` extra |
| Jev / TypeSafe | `typesafe-sdk>=0.7,<1` | Dedicated adversarial contract tests on Python 3.12 | Optional `schemarouter[jev]` extra; no live API call in required CI |
| Laya | `laya>=0.3.6,<1` | Dedicated adversarial adapter tests plus optional-extra install on Python 3.12 | Optional `schemarouter[laya]` extra; required CI does not download model weights |
| Ollama decision backend | Ollama structured-output HTTP API | Mock-transport adversarial tests in the core suite | No SDK dependency; live model benchmark is explicit and non-blocking |
| MCP | `mcp>=2,<3` | Real Streamable HTTP integration against a local server | Optional `schemarouter[mcp]` extra |
| OpenTelemetry | `opentelemetry-api/sdk>=1.44,<2` | In-memory span hierarchy, error status, and privacy tests | Optional `schemarouter[otel]` extra; core has no OTel dependency |
| OpenAPI | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OpenAPI SDK dependency |
| OPTIMADE | Built-in adapter | Deterministic fixtures + scheduled public smoke | No OPTIMADE client dependency |
| Published PyPI package | Latest stable wheel + sdist | Scheduled/manual external smoke | Installs from PyPI in a fresh runner, runs `pip check`, and executes a public API scenario outside the checkout |
| Published lightweight extras | Latest stable `mcp` + `jev` + `otel` extras | Scheduled/manual external smoke | Installs only those three extras from PyPI and validates their SDK integration surface without relying on framework transitive dependencies |
| Published integration extras | Latest stable `mcp` + `langchain` + `langgraph` + `llamaindex` + `jev` + `otel` extras | Scheduled/manual external smoke | Resolves the combined published extras from PyPI, validates MCP/Jev/OpenTelemetry SDK integration imports, and executes the three framework bridges outside the checkout |

Before widening an upper bound or lowering a minimum supported version, the relevant integration
tests must pass against that target and the change must be documented in release notes.

## Required CI

Every pull request runs the blocking `CI` workflow with:

- Python 3.10 / 3.11 / 3.12 / 3.13 / 3.14 core tests;
- a Windows + Python 3.14 core smoke test;
- warnings-as-errors;
- Pyright static type checking across the packaged surface;
- full-suite branch coverage with an 84% blocking floor and a retained XML artifact;
- a minimum-runtime-dependency job that exercises the declared lower bounds;
- executable core quickstart;
- wheel and sdist build + metadata checks;
- clean-environment installation and quickstart smoke tests from both wheel and sdist;
- LangChain integration contract tests and `examples/langchain_quickstart.py`;
- LangGraph `StateGraph` sync/async contract tests and `examples/langgraph_quickstart.py`;
- LlamaIndex integration contract tests and `examples/llamaindex_quickstart.py`;
- bounded candidate and field-selection planner tests, including identifier preservation,
  malformed/unknown IDs, abstention, sync/async paths, and deterministic fallback;
- Jev adapter adversarial tests with the official SDK installed but no external API dependency;
- Laya adapter adversarial tests with the official package installed but no model-weight download;
- Ollama bounded-decision adversarial tests using a local mock HTTP transport;
- real MCP Streamable HTTP integration using the official SDK and a local HTTP server;
- OpenTelemetry integration tests using the SDK in-memory exporter;
- strict MkDocs build.

A separate `Python Preview` workflow runs Python 3.15 RC on pull requests and `main` pushes.
It is intentionally outside the blocking `CI` workflow and has a bounded runtime. Failures remain
visible as forward-compatibility signals but cannot stall release publication.

The top-level Release workflow consumes a successful current-`main` `CI` result before it
resolves the release tag and builds artifacts. This keeps publication coupled to deterministic
release blockers without waiting on preview-only interpreter experiments. After GitHub Release and
PyPI publication both succeed, the workflow re-installs that exact release version from PyPI as a
wheel, forced sdist, isolated `mcp,jev,otel` environment, and combined integration-extras
environment, then executes the published-package smoke outside the checkout. PyPI index propagation is handled by a bounded retry window rather than by
accepting a different version.

## Integration maintenance policy

Optional ecosystem bridges remain thin adapters around SchemaRouter's existing trust boundary.

- The core package must import and run without LangChain, LangGraph, LlamaIndex, Jev/TypeSafe,
  Laya, MCP, or OpenTelemetry installed.
- Integration modules use lazy imports and bounded dependency ranges.
- An integration may translate framework/provider metadata, but execution must still flow through
  SchemaRouter schema identity, policy, binding checks, and validation.
- If a newly released upstream version breaks compatibility inside a declared range, the range may
  be narrowed temporarily while the bridge is repaired. The change must be documented.
- New upstream major versions are unsupported until dedicated CI coverage is added.
- Public examples and documented security invariants are compatibility contracts.

### Package layout decision

For now, the LangChain, LangGraph, and LlamaIndex bridges stay inside the main distribution as
optional extras: `schemarouter[langchain]`, `schemarouter[langgraph]`, and
`schemarouter[llamaindex]`.

A separate package such as `langchain-schemarouter` should be introduced only if at least one of
these becomes true:

1. the integration needs an independent release cadence;
2. dependency pressure would otherwise widen the core package's maintenance surface materially;
3. upstream maintainers require a dedicated distribution for discoverability or certification;
4. the integration grows beyond a thin translation layer.

The Jev and Laya providers follow the same principle: they remain optional `schemarouter[jev]` and
`schemarouter[laya]` extras and do not make either provider runtime a core dependency. OpenTelemetry
likewise remains an optional
`schemarouter[otel]` exporter integration.

## External compatibility checks

The `Compatibility Smoke` workflow runs weekly and can also be triggered manually for public
OpenAPI/OPTIMADE services and the latest stable SchemaRouter package published on PyPI. The PyPI
smoke separately forces wheel and sdist installation, runs `pip check`, and executes a public API
scenario from outside the repository checkout. A dedicated isolated smoke installs only
`schemarouter[mcp,jev,otel]` so those integrations cannot accidentally rely on framework
transitive dependencies. A companion combined published-extras smoke resolves
`schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel]` from PyPI and executes each framework
bridge through the installed stable package rather than the source checkout.

External-service failures are compatibility signals, not pull-request blockers, because third-party
availability is outside SchemaRouter's control.

Live decision-model benchmarking is intentionally excluded from required CI. Run Jev explicitly
with `TYPESAFE_API_KEY` and `--jev`, run local Laya with `--laya`, or run a trusted local Ollama
model with `--ollama-model <installed-model>`.

## Live OpenAPI smoke

The public OpenAPI smoke imports and executes against APIs.guru.

The default source is:

```text
https://api.apis.guru/v2/openapi.yaml
```

Set `SCHEMAROUTER_LIVE_OPENAPI_URL` when running the smoke script locally to use another compatible
service.

## Release interpretation

A green required CI proves package and protocol behavior under controlled conditions. Recent green
external smokes provide additional evidence that remote adapters remain compatible with real public
services. Both should be reviewed before a release candidate is promoted.


## Scheduled live-smoke artifacts

The non-blocking public OpenAPI, OPTIMADE, published-PyPI, and published-integration compatibility
jobs emit one
machine-readable JSON artifact per smoke job. Reports include a schema version, UTC generation time, SchemaRouter version,
adapter/source identity, runtime environment, success/failure state, and bounded success details.
On failure, only the exception type is recorded; exception messages are intentionally omitted.

GitHub Actions retains these artifacts for 30 days. This makes compatibility drift inspectable
without turning live third-party availability into a release-blocking gate. The raw JSON remains the
source of truth for any later history/dashboard tooling.

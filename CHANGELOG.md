# Changelog

All notable changes to SchemaRouter are documented here.

The project is pre-1.0 and follows the compatibility rules in
[`docs/versioning.md`](docs/versioning.md).

## Unreleased

### Changed

- post-release development has resumed as `0.3.0a2.dev0`; published `0.3.0a1` artifacts remain
  immutable.

## 0.3.0a1 - 2026-09-22

### Added

- provider-neutral bounded `DecisionBackend` contracts with deterministic fallback;
- optional `JevDecisionBackend` backed by TypeSafe System One through `schemarouter[jev]`;
- optional LlamaIndex `FunctionTool` integration;
- runnable LangChain and LlamaIndex integration examples enforced in CI;
- provider-neutral decision-routing benchmark harness covering accuracy, abstention, latency,
  token usage, and optional cost estimation;
- explicit ecosystem compatibility matrix and integration maintenance policy;
- Korean project overview in `README.ko.md`;
- Python 3.13 and 3.14 core CI coverage;
- a non-blocking Python 3.15 release-candidate preview;
- a Windows + Python 3.14 smoke surface;
- a Pyright static-type gate for the typed package surface;
- full-suite branch-coverage reporting with an 82% blocking floor;
- declared lower-bound runtime dependency testing;
- clean wheel and sdist installation smoke tests;
- a checked-in 144-case multilingual/adversarial decision-routing corpus with JSON/CSV output,
  category metrics, invalid-plan rate, abstention/fallback tracking, and p50/p95 latency;
- machine-readable OpenAPI compatibility reports for partial/unsupported constructs;
- authenticated MCP trusted-header and custom client-factory transport boundaries;
- trusted sync/async per-call approval callbacks;
- per-run execution budgets for logical calls, attempts, remote attempts, elapsed time, per-tool
  quotas, and application-defined cost units;
- optional privacy-preserving OpenTelemetry run/tool span export;
- explicit allowlisted third-party adapter plugins through `schemarouter.adapters` entry points.

### Changed

- release preparation now uses explicit PEP 440 release versions while normal post-release
  development returns to a `.dev0` version;
- release automation now derives version, release title, release-note path, prerelease state, and
  artifact verification from `pyproject.toml` instead of hard-coded release literals;
- release publication now consumes a successful current-`main` CI result, verifies or creates the
  annotated version tag, and clean-installs both wheel and sdist artifacts before publication;
- superseded pull-request CI runs are cancelled automatically to avoid stale validation consuming
  runner capacity;
- releasable `main` commits are automatically published by the top-level Release workflow only
  after green CI, current-head verification, release-note/changelog validation, and duplicate-tag
  checks; existing unpublished tags may be resumed only from a compatible ancestor SHA.

### Security

- OpenAPI runtime responses are now streamed through a bounded reader with a 16 MiB default limit,
  enforcing the bound both from declared `Content-Length` and actual bytes received;
- Jev option IDs are validated before confidence-based abstention, so unknown IDs always fail
  closed;
- Jev credentials remain SDK client configuration and are never placed in model state;
- `DecisionOption.metadata` is not forwarded to Jev;
- provider failures can deterministically fall back without weakening execution policy;
- MCP credentials are rejected in URLs and remain outside tool/planner metadata;
- MCP protocol-controlled headers cannot be overridden through trusted runtime headers;
- adapter entry points are metadata-only during discovery and are never auto-imported;
- OpenTelemetry export omits payload values, RunConfig metadata, tags, and exception messages;
- approval callback failures and execution budget exhaustion fail closed.

## 0.2.0a1 - 2026-09-20

### Added

- pluggable structured-source `AdapterRegistry` with explicit and priority-based auto discovery;
- OPTIMADE v1 discovery through base and entry-type info endpoints;
- OPTIMADE field-aware execution that maps planned fields to `response_fields`;
- call-aware invoker support for protocol adapters that need the full `ToolCall`;
- typed tool, endpoint, parameter, response-field, plan, and result contracts;
- namespaced versioned registry;
- schema-aware planning with recall-preserving field projection;
- provider-neutral model-assisted query analysis;
- OpenAPI 3.x URL ingestion and guarded HTTP execution;
- MCP tool discovery and execution;
- evidence-grounded proposals for human-readable API documentation;
- runtime JSON Schema validation for arguments and raw outputs;
- schema and invoker-binding drift detection;
- fail-closed execution policy for mutations, destructive calls, and unclassified remote tools;
- Runnable-style `invoke`, `batch`, `stream`, and typed event APIs;
- run configuration, concurrency control, and safe retry policy;
- typed Python callable registration with `@schema_tool`;
- optional LangChain `StructuredTool` integration;
- framework maturity, architecture, release, and versioning documentation;
- MIT licensing and package metadata;
- MkDocs Material documentation site with guides, recipes, and generated API reference;
- SchemaRouter brace-and-routing-hub brand system with light/dark marks, lockups, favicon, and
  social preview source artwork.

### Security

- separated schema-fetch credentials from runtime API credentials;
- restricted schema redirects and runtime API origins;
- blocked model/tool control of sensitive runtime headers;
- redacted event payloads by default;
- prevented automatic retries for non-read-only calls.

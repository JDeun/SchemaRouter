# Versioning and compatibility

SchemaRouter follows Semantic Versioning for released Python packages.

The project is currently pre-1.0. During the 0.x series, the public API is still being shaped, but
compatibility changes must remain deliberate and documented.

## Development branch versions

The default branch uses a PEP 440 development version for unreleased work. For example, after
`0.2.0a1` is published, `main` may identify as `0.3.0.dev0` until the next release is cut.

Release tags must match the version declared in `pyproject.toml`.

After a releasable version is merged to `main`, the top-level `Release` workflow waits for the
normal `CI` workflow to succeed. It verifies that the tested SHA is still the current `main`
head, rejects `.dev` versions, requires a matching `docs/releases/<version>.md` file and dated
changelog heading, and creates `v<version>` only when that tag does not already exist.

If a tag already exists without a GitHub release, publication can resume from that tagged SHA only
when it is an ancestor of the successful current `main` and contains the same package version.
This makes interrupted releases recoverable without silently moving an existing tag.

The same top-level workflow then builds wheel and sdist artifacts from the resolved release SHA,
clean-installs and smoke-tests both artifacts, creates the GitHub release, and publishes through the
configured PyPI Trusted Publisher. Build jobs remain unprivileged; only the dedicated publishing job
receives OIDC `id-token: write` permission.

This keeps source checkouts distinguishable from released artifacts, removes manual tag creation,
and preserves PyPI Trusted Publishing on the stable `.github/workflows/release.yml` identity.

## Public API

The following are treated as public when they are documented and exported from the top-level
`schemarouter` package or an explicitly documented integration module:

- typed contracts such as `ToolSpec`, `EndpointSpec`, `PlanRequest`, and `ExecutionPlan`;
- `SchemaRouter` public methods and execution verbs;
- `RunConfig`, `RetryPolicy`, `ExecutionBudget`, `RunEvent`, and `ExecutionPolicy`;
- documented approval, MCP transport-factory, compatibility-report, and adapter-plugin contracts;
- documented adapters and optional integration entry points.

Underscore-prefixed objects and undocumented internal helpers are not compatibility contracts.

## 0.x policy

- Patch releases should remain backward-compatible except for security or correctness defects that
  would otherwise violate a fail-closed invariant.
- Minor releases may introduce breaking changes while the framework is pre-1.0.
- Breaking changes must be listed in the changelog with a migration note.
- Serialized plans should not be assumed portable across breaking minor versions unless an explicit
  codec/version contract is documented.

## Deprecation policy

Once an API has appeared in a non-alpha 0.x release, planned removals should normally:

1. be documented as deprecated;
2. remain available for at least one minor release when technically safe;
3. include a replacement or migration path;
4. be removed only in a subsequent minor release.

Security-sensitive behavior may fail closed immediately when preserving the old behavior would
create an authorization, credential, schema-integrity, or side-effect risk.

## Integration compatibility

Optional integrations are versioned separately from the core trust model.

- The core package must import and operate without LangChain, LlamaIndex, Jev/TypeSafe, MCP, or
  OpenTelemetry extras installed.
- Integration dependencies use bounded major-version ranges.
- The declared lower bounds of core runtime dependencies are exercised in required CI.
- Integration CI must exercise the supported dependency range before a release.
- An integration must route execution through SchemaRouter policy and validation rather than calling
  the underlying transport directly.

## Compatibility priorities

When trade-offs are unavoidable, use this order:

1. execution authority and credential safety;
2. schema/fingerprint correctness;
3. deterministic plan semantics;
4. public API compatibility;
5. convenience behavior.

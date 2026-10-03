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
clean-installs and smoke-tests both artifacts, generates the SPDX SBOM plus
`SHA256SUMS.txt` / `release-manifest.json`, creates the GitHub release, and publishes through the
configured PyPI Trusted Publisher. The manifest records the exact source SHA and artifact digests so
those values do not need to be copied into documentation manually. Build jobs remain unprivileged;
only the dedicated publishing job receives OIDC `id-token: write` permission.

This keeps source checkouts distinguishable from released artifacts, removes manual tag creation,
and preserves PyPI Trusted Publishing on the stable `.github/workflows/release.yml` identity.

## Public API

The following are treated as public when they are documented and exported from the top-level
`schemarouter` package or an explicitly documented integration module:

- typed contracts such as `ToolSpec`, `EndpointSpec`, `PlanRequest`, `CapabilityCandidate`,
  `CapabilityRetrieval`, `StateAwareCapabilityRetrieval`,
  `StateConditionedCapabilityRetrieval`, and `ExecutionPlan`;
- `SchemaRouter` public registration/retrieval/planning/execution methods, including
  `add_provider`, `retrieve`, `aretrieve`, `retrieve_executable`,
  `aretrieve_executable`, `retrieve_state_aware`, `reretrieve_state_aware`, and the execution
  verbs;
- documented provider-profile, capability-snapshot/publication, portable artifact/migration, and
  capability decision-trace contracts;
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

## Persisted SQLite compatibility

`SQLiteRegistry` and `SQLiteRunTraceStore` have an explicit storage-format contract independent
from the package version and from the registry's logical mutation counter.

During the pre-1.0 series:

- the current persisted storage format is versioned explicitly in SQLite metadata;
- ToolSpec and RunEvent document formats are versioned separately from the database/container
  format so future document migrations can be deterministic;
- the immediately preceding unversioned legacy format (v0) is supported as an upgrade source;
- opening a valid v0 store automatically performs the current v0 -> v1 metadata migration in one
  SQLite transaction **after validating every legacy document and replay invariant**;
- the current v0 -> v1 migration does not rewrite ToolSpec or RunEvent JSON, does not change the
  registry logical version, and does not create execution bindings or other runtime authority;
- unknown/newer storage or document versions fail closed with `StorageFormatError` rather than
  attempting partial decoding;
- incomplete/corrupt version metadata also fails closed instead of guessing;
- each successful component migration is recorded in migration history.

For production databases, use `schemarouter storage inspect` before an upgrade and
`schemarouter storage migrate` when an explicit preflight/backup is preferred. The migration
command creates a SQLite-consistent backup by default before changing a legacy component. Keep
that backup until the upgraded service has passed application-level verification.

A future migration that rewrites or drops persisted document content must provide an explicit
backup/recovery path and release-note migration guidance before it can become automatic.

## Portable capability artifact and snapshot compatibility

Portable capability graph data has an explicit format lifecycle separate from both the Python
package version and SQLite storage versions.

During the pre-1.0 series:

- the current `CapabilityGraphArtifact` format is `1.1`;
- artifact `1.0` is a supported migration source and is validated before conversion;
- legacy 1.0 edge metadata migrates as `origin="external"` rather than being promoted to derived
  execution authority;
- the current versioned snapshot document format is `1.0`;
- a raw JSON dump of the pre-envelope public `CapabilityGraphSnapshot` model is supported as the
  `legacy-unversioned` migration source after its existing `snapshot_id` is verified;
- unknown/newer artifact or snapshot document versions fail closed;
- migration is deterministic and idempotent for supported inputs;
- credentials, invokers, live health state, and execution authority are never reconstructed by a
  format migration.

Use `schemarouter artifact inspect/migrate` and `schemarouter snapshot inspect/migrate` for
operator-facing validation and conversion. Migration writes a new file by default and requires
explicit `--overwrite` before replacing an existing destination.

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

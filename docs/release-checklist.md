# Release checklist

Use this checklist before promoting a SchemaRouter alpha, beta, release candidate, or stable tag.

## Blocking gates

- [ ] Core CI passes on every supported Python version.
- [ ] Warnings are treated as failures.
- [ ] Static type checking passes for the typed package surface.
- [ ] The 82% branch-coverage floor passes.
- [ ] Minimum declared runtime dependencies pass the core suite.
- [ ] Optional integration CI passes, including LangChain, LlamaIndex, Jev, MCP, and OpenTelemetry.
- [ ] Linux core CI passes on Python 3.10 through 3.14.
- [ ] The Windows + Python 3.14 smoke job passes.
- [ ] The Python 3.15 preview is reviewed for forward-compatibility signals.
- [ ] Quickstart examples execute successfully.
- [ ] Package wheel and sdist build successfully.
- [ ] Wheel and sdist both install and run the quickstart in clean environments.
- [ ] Package metadata can be inspected without errors.
- [ ] Public API changes are reflected in README and architecture docs.
- [ ] CHANGELOG contains the release entry and migration notes for breaking changes.
- [ ] Security invariants have regression tests.
- [ ] SECURITY.md still matches URL, credential, retry, and observability behavior.
- [ ] No credentials, tokens, fixtures containing secrets, or generated local state are committed.
- [ ] MIT license metadata and the root LICENSE file are present in the release artifact.
- [ ] README, documentation header, favicon, and brand guide use the approved SchemaRouter mark.
- [ ] The GitHub repository social preview is exported from the approved 1280×640 brand source and set in repository settings.

## Compatibility gates

- [ ] A recent public OpenAPI live smoke is green.
- [ ] A recent public OPTIMADE live smoke is green.
- [ ] The real MCP Streamable HTTP integration job is green when the MCP extra is part of the release.
- [ ] Optional framework/provider integration jobs are green for every extra included in the release.
- [ ] Cross-origin OpenAPI behavior is tested with explicit local approval.
- [ ] Schema drift and stale binding tests pass.
- [ ] Input/output JSON Schema validation tests pass.
- [ ] Mutation/destructive policy tests pass.
- [ ] Retry tests prove that non-read-only operations are not retried by default.
- [ ] Event tests prove payload redaction is the default.
- [ ] OpenTelemetry tests prove payload values and exception messages are not exported.
- [ ] Approval tests prove missing/denied/error decisions fail closed.
- [ ] Budget tests prove retries consume attempt/remote/cost limits before invocation.
- [ ] Adapter plugin tests prove discovery does not import code and loading requires an allowlist.
- [ ] MCP auth tests prove trusted credentials remain transport-local and protected headers cannot be overridden.
- [ ] OpenAPI compatibility tests make unsupported semantics visible.

## Release mechanics

- [ ] Replace the development version in `pyproject.toml` with the intended release version.
- [ ] Add `docs/releases/<version>.md`; release metadata is derived from this version automatically.
- [ ] The release commit is merged to `main` and the normal CI workflow is green.
- [ ] The top-level `Release` workflow consumes that successful `main` CI event and verifies that
  the tested SHA is still the current `main` head.
- [ ] The release workflow rejects `.dev` versions and requires matching release notes and a dated
  changelog heading.
- [ ] If `v<version>` does not already exist, the release workflow creates an annotated tag at the
  exact green `main` SHA.
- [ ] If the tag already exists but the GitHub release does not, the workflow may resume from that
  tagged SHA only when it is an ancestor of the green current `main` and carries the same version.
- [ ] Build wheel and sdist from the resolved release SHA in an unprivileged job.
- [ ] Clean-install and smoke-test both built artifacts before publication.
- [ ] Publish GitHub release assets and PyPI artifacts from separate jobs; only the PyPI job receives
  OIDC `id-token: write` permission.
- [ ] Confirm the PyPI Trusted Publisher is configured for the `pypi` GitHub environment.
- [ ] Publish to the package index only after all blocking gates are green.
- [ ] Verify install/import in a clean environment.

## Post-release

- [ ] Confirm documentation examples match the released package.
- [ ] Record any compatibility regressions as release blockers for the next patch.
- [ ] Keep security/correctness fixes separate from convenience refactors where practical.

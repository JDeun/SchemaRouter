# Release checklist

Use this checklist before promoting a SchemaRouter alpha, beta, release candidate, or stable tag.

## Blocking gates

- [ ] Core CI passes on every supported Python version.
- [ ] Warnings are treated as failures.
- [ ] Static type checking passes for the typed package surface.
- [ ] Optional integration CI passes.
- [ ] Quickstart examples execute successfully.
- [ ] Package wheel and sdist build successfully.
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

## Release mechanics

- [ ] Replace the development version in `pyproject.toml` with the intended release version.
- [ ] Add `docs/releases/<version>.md`; release metadata is derived from this version automatically.
- [ ] Build from a clean checkout.
- [ ] Run the full test suite against the built artifact.
- [ ] Create an annotated Git tag.
- [ ] Publish the tag/release notes.
- [ ] Confirm the PyPI Trusted Publisher is configured for the `pypi` GitHub environment.
- [ ] Publish to the package index only after all blocking gates are green.
- [ ] Verify install/import in a clean environment.

## Post-release

- [ ] Confirm documentation examples match the released package.
- [ ] Record any compatibility regressions as release blockers for the next patch.
- [ ] Keep security/correctness fixes separate from convenience refactors where practical.

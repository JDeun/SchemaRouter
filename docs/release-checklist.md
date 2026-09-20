# Release checklist

Use this checklist before promoting a SchemaRouter alpha, beta, release candidate, or stable tag.

## Blocking gates

- [ ] Core CI passes on every supported Python version.
- [ ] Warnings are treated as failures.
- [ ] Optional integration CI passes.
- [ ] Quickstart examples execute successfully.
- [ ] Package wheel and sdist build successfully.
- [ ] Package metadata can be inspected without errors.
- [ ] Public API changes are reflected in README and architecture docs.
- [ ] CHANGELOG contains the release entry and migration notes for breaking changes.
- [ ] Security invariants have regression tests.
- [ ] SECURITY.md still matches URL, credential, retry, and observability behavior.
- [ ] No credentials, tokens, fixtures containing secrets, or generated local state are committed.
- [ ] License is explicitly selected and a LICENSE file exists.

The license decision is intentionally unresolved in v0.1 development. Do not publish the package
until the project owner selects the license.

## Compatibility gates

- [ ] A recent public OpenAPI live smoke is green.
- [ ] The real MCP Streamable HTTP integration job is green when the MCP extra is released.
- [ ] Cross-origin OpenAPI behavior is tested with explicit local approval.
- [ ] Schema drift and stale binding tests pass.
- [ ] Input/output JSON Schema validation tests pass.
- [ ] Mutation/destructive policy tests pass.
- [ ] Retry tests prove that non-read-only operations are not retried by default.
- [ ] Event tests prove payload redaction is the default.

## Release mechanics

- [ ] Update the version in `pyproject.toml`.
- [ ] Build from a clean checkout.
- [ ] Run the full test suite against the built artifact.
- [ ] Create an annotated Git tag.
- [ ] Publish the tag/release notes.
- [ ] Publish to the package index only after the license gate is resolved.
- [ ] Verify install/import in a clean environment.

## Post-release

- [ ] Confirm documentation examples match the released package.
- [ ] Record any compatibility regressions as release blockers for the next patch.
- [ ] Keep security/correctness fixes separate from convenience refactors where practical.

# Trust, stability, and public evidence

SchemaRouter separates **stable product guarantees**, **release/process evidence**, and **research
evidence**. This page is the verification index for engineers who want to check the project without
relying on marketing copy.

## Current stable release

| Item | Verified public state |
| --- | --- |
| Stable version | `0.14.0` |
| Release date | 2026-10-02 |
| Status | Beta / pre-1.0 |
| Python | 3.10–3.14 are release-blocking CI targets; 3.15 is a non-blocking preview |
| License | MIT |
| Release | [SchemaRouter 0.14.0](https://github.com/JDeun/SchemaRouter/releases/tag/v0.14.0) |
| Stable-core contract | [Stable core](../stable-core.md) |
| Security policy | [SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md) |

For 0.14.0 and later, the exact release source SHA and artifact digests are recorded by the
machine-generated `release-manifest.json` and `SHA256SUMS.txt` attached to the GitHub Release.
The annotated tag is not described as GPG-signed; artifact provenance is provided by GitHub artifact
attestations.

## Historical 0.13.0 artifact digests

The 0.13.0 release predates the generated manifest and is retained here as a fixed historical
digest record:

| Artifact | SHA-256 |
| --- | --- |
| `schemarouter-0.13.0-py3-none-any.whl` | `1fad74f9b0604a3a8309fe71a729670aed4c0b37be2980e00c652f702ffb4ed5` |
| `schemarouter-0.13.0.tar.gz` | `5436dfae9058504fa8ef2c56ddad57a151668bf7d996ef5ddab3d329e9c4a659` |
| `schemarouter-0.13.0.spdx.json` | `a1c62770a10d33cc366d487d696ed67dcf220e930cbbd087d9ca69e6a96a760d` |

The release workflow:

1. accepts only a successful CI run for the current `main` SHA;
2. rejects development versions and requires matching release notes/changelog metadata;
3. builds wheel and sdist from the resolved release SHA;
4. clean-installs and smoke-tests both build artifacts;
5. generates an SPDX JSON SBOM;
6. creates GitHub artifact provenance attestations for the distributions and an SBOM attestation;
7. publishes through PyPI Trusted Publishing;
8. downloads the exact published version from public PyPI;
9. compares the public wheel/sdist digests with the trusted build artifacts;
10. installs the published wheel, sdist, lightweight extras, and combined integration extras.

Implementation:
[release.yml](https://github.com/JDeun/SchemaRouter/blob/main/.github/workflows/release.yml)

A local verifier can additionally download a release artifact and compare its SHA-256 with the table
above. When GitHub CLI attestation verification is available:

```bash
gh attestation verify schemarouter-0.14.0-py3-none-any.whl --repo JDeun/SchemaRouter
```

The repository release checklist treats provenance, SBOM, public-PyPI digest equivalence, and
post-publish installation as explicit release mechanics rather than optional documentation tasks.

Beginning with 0.14.0, the release workflow also attaches two machine-generated
records so checksums are not copied into documentation by hand:

- `SHA256SUMS.txt` — SHA-256 digests for wheel, sdist, and SPDX SBOM;
- `release-manifest.json` — package version, tag, exact source commit, artifact names, sizes, and
  SHA-256 digests.

Those release assets are the canonical per-release checksum record. The static 0.13.0 table above
is historical evidence for the last release that predates this manifest.

## CI and security automation

The protected product surface is tested through independent workflows rather than one decorative
badge.

### Required CI matrix

The main CI workflow includes:

- Python 3.10, 3.11, 3.12, 3.13, and 3.14;
- Windows + Python 3.14 smoke coverage;
- branch coverage with an 84% floor;
- minimum dependency testing;
- static type checking;
- built wheel/sdist clean-environment acceptance;
- LangChain and LangGraph integration;
- LlamaIndex integration;
- MCP integration;
- Jev/System-One, Laya, and OpenTelemetry integration jobs;
- dependency auditing;
- strict documentation builds.

Python 3.15 is intentionally a preview signal rather than a release blocker.

### Independent security automation

The repository also runs:

- CodeQL;
- a separate Security Audit workflow;
- OpenSSF Scorecard;
- immutable commit pinning for external GitHub Actions;
- regression tests around credentials, policy, destructive operations, schema drift, bindings,
  redaction, budgets, and authentication contracts.

A green CI badge is therefore not treated as evidence that every security question is solved. The
security model and reporting path remain documented separately in
[SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md).

## Stable runtime guarantees

The stable product claim is intentionally narrower than "the router is always correct."

### Bounded authority

Retrieval and model-assisted decisions do **not** grant execution authority. Executable tools,
endpoints, fields, parameters, credentials, policies, and side-effect permissions come from trusted
registered contracts and local application state.

### Validation before and after invocation

SchemaRouter validates:

- required/allowed arguments;
- current schema and tool fingerprints;
- binding readiness;
- local policy and approval requirements;
- raw provider output against the registered output schema;
- declared field projection before returning a `ToolResult`.

### Destructive operations fail closed

Mutation/destructive/unclassified remote operations are not silently treated as safe reads.
Permission and approval semantics remain local and explicit.

### Schema drift does not silently replace authority

Remote metadata changes are compared against the accepted contract. Identical contracts require no
write, compatible changes may be explicitly accepted, and breaking/security-relevant drift is held
for review. Stale bindings fail closed.

### Runtime invariants fail closed

Production runtime contract violations raise explicit invariant errors rather than relying on Python
`assert` statements that can be optimized away. This hardening is tracked in
[#627](https://github.com/JDeun/SchemaRouter/issues/627).

Other public hardening examples include:

- [#594 — schema-watch contract/source credential cross-binding](https://github.com/JDeun/SchemaRouter/issues/594);
- [#602 — authentication requirements in the canonical execution contract](https://github.com/JDeun/SchemaRouter/issues/602).

All three are closed in the current development history.

## Compatibility evidence

Protocol compatibility and routing quality are different evidence classes.

The scheduled/manual live compatibility matrix exercises:

- APIs.guru OpenAPI;
- COD OPTIMADE;
- Rick and Morty GraphQL;
- OData.org V4;
- pinned OpenRPC / JSON-RPC reference implementation;
- pinned MCP Streamable HTTP reference implementation.

These checks produce machine-readable compatibility evidence, but third-party provider uptime is not
a release-blocking dependency.

See [Live compatibility matrix](../guides/live-compatibility-matrix.md) and
[Compatibility testing](../compatibility.md).

## Research evidence: what may be claimed

Research evidence is not promoted into stable product guarantees merely because a benchmark is
positive.

The canonical 0.14 evidence checkpoint currently records, among other results:

| Evidence | Result | Allowed interpretation |
| --- | --- | --- |
| B1 controlled Qwen3-0.6B | SR-5 task pass 91.30% vs FULL 68.48%; SR-5 schema-token ratio 5.42%; required-route recall 100% | controlled mechanism evidence on the frozen 23-task surface |
| Structural K3 vs K5 | K3 task-pass delta -3.2609 pp; preregistered -2 pp promotion floor failed | negative evidence; K3 is not promoted |
| Unauthorized destructive executions in the reported B1/K3 evidence | 0 | limited to those recorded experimental surfaces |

The B1 result is **not** a claim of population-level production superiority, all-agent
generalization, or final-answer factual quality. The structural K3 result is retained publicly as a
negative result rather than hidden.

Canonical sources:

- [0.14 paper-evidence checkpoint](../research/0.14-paper-evidence-checkpoint.md)
- [Research evidence package](../research/paper-evidence-package.md)
- `benchmarks/research-experiment-ledger.json`

Issue [#15](https://github.com/JDeun/SchemaRouter/issues/15) remains open for reproducible **live
decision-backend** measurements. Until that work is terminal, this page does not claim that Jev,
Laya, Ollama, hosted models, or any other decision backend is superior in live routing quality,
latency, token use, or cost.

## Public report and hardening log

This page distinguishes project-discovered hardening work from externally reported incidents.

| Source | Item | Status |
| --- | --- | --- |
| project hardening | #594 credential/source cross-binding boundary | closed |
| project hardening | #602 canonical authentication contract | closed |
| project hardening | #627 fail-closed runtime invariant checks | closed |

As of 2026-10-01, no **publicly disclosed external** security/reliability report has been identified
as such in the repository issue history reviewed for this page. This statement does not disclose or
deny the existence of private vulnerability reports. A public advisory or external report must be
added to this table once disclosure is appropriate, including status, affected versions, fix
version, and advisory/reference link.

Sensitive vulnerabilities must be reported through
[GitHub private vulnerability reporting](https://github.com/JDeun/SchemaRouter/security/advisories/new),
not through a public issue.

## External validation still needed

Repository-owned CI is necessary but not independent validation. Stronger evidence would include:

- downstream projects running SchemaRouter in their own CI;
- independent reproduction of benchmark artifacts;
- external maintainer review of framework integrations;
- reproducible integration PRs in real agent/RAG projects;
- public talks/blogs that link runnable code and disclose limitations;
- external security review or responsibly disclosed vulnerability reports.

These are adoption/evidence goals, not claims that they have already happened. External adopter and
case-study work is tracked separately in #584.

## Verification rule for future claims

A public claim should resolve to at least one of:

- a released artifact;
- a protected CI/security workflow;
- a versioned compatibility report;
- a reproducible benchmark artifact/ledger row;
- a documented external adopter or independent reproduction.

If it cannot, the claim belongs in a roadmap or hypothesis section rather than the stable product
description.

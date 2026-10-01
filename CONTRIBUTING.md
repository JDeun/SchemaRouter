# Contributing to SchemaRouter

SchemaRouter is a focused **typed capability retrieval and schema-aware execution layer** for LLM/RAG
agents. Contributions should strengthen that boundary without turning the project into a second
general-purpose agent framework.

This guide is intentionally task-oriented: a first-time contributor should be able to choose a
bounded change, run the relevant checks, and open a reviewable pull request without private setup
instructions.

## Before opening code

Choose the narrowest matching path:

- reproducible defect -> use the **Bug report** issue form;
- new framework/runtime bridge -> use **Integration request**;
- new structured provider/protocol -> use **Provider / schema adapter**;
- benchmark or research result -> use **Benchmark / research evidence**;
- security-sensitive defect -> use
  [GitHub private vulnerability reporting](https://github.com/JDeun/SchemaRouter/security/advisories/new),
  never a public issue.

Open-ended feature requests should first identify a concrete user-visible gap, trust boundary, or
interoperability requirement. "Support provider X" is not enough unless the structured schema source,
execution binding, and authority model are clear.

## Development setup

SchemaRouter supports Python 3.10-3.14 in release-blocking CI. Python 3.15 is preview-only.

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
```

Run the fast local baseline:

```bash
ruff check .
pytest -q -m "not mcp_integration"
python examples/quickstart.py
```

For the complete typed surface and ordinary optional integrations:

```bash
pip install -e ".[dev,mcp,langchain,langgraph,llamaindex,jev,otel]"
pyright
pytest -q --cov=schemarouter --cov-branch --cov-report=term-missing
```

Laya has a separate CPU-only CI environment because its PyTorch dependency is intentionally not
installed into the ordinary development environment.

## Pick the smallest relevant test surface

Do not wait for the entire CI matrix before checking an obvious local failure. Run the smallest
surface that proves the change, then widen as needed.

| Change | Minimum local evidence |
| --- | --- |
| core model/registry/planner/runtime | focused unit tests + `pyright` |
| adapter/protocol | adapter tests + invalid input/output + stale binding/fingerprint cases |
| framework integration | focused integration tests + runnable example |
| CLI/docs | focused CLI tests where applicable + `mkdocs build --strict` |
| storage/migration | focused storage tests + legacy/current format paths |
| benchmark/research | frozen workload + machine-readable artifact + claim boundary |
| dependency/package metadata | focused test + clean wheel/sdist acceptance when practical |

Required CI remains authoritative for the supported Python/Windows/package/integration matrix.

## Architecture map

The main ownership boundaries are:

```text
schemarouter.models            typed tool / endpoint / plan contracts
schemarouter.registry          versioned capability catalog
schemarouter.planner           bounded field/tool/endpoint selection
schemarouter.policy            local side-effect and approval authority
schemarouter.validation        JSON Schema validation
schemarouter.executor          validation + binding + policy + invocation boundary
schemarouter.runtime           high-level invoke/batch/stream facade
schemarouter.adapters          built-in and plugin source/protocol adapters
schemarouter.ingestion         adapter dispatch and trusted registration
schemarouter.integrations      optional framework/runtime bridges
schemarouter.decision_plugins  explicit third-party decision backends
schemarouter.schema_watch      bounded schema refresh/drift lifecycle
schemarouter.storage           persisted registry/run-trace formats
```

Read [Architecture](https://jdeun.github.io/SchemaRouter/architecture/) before changing trust or
module boundaries.

## Extension points

Prefer an existing extension point over modifying core dispatch for one provider.

### SourceAdapter / provider schema adapter

Use this when a structured source can be compiled into normal `ToolSpec` / `EndpointSpec`
contracts plus a trusted invoker.

- built-ins live under `schemarouter.adapters`;
- third-party packages may expose `schemarouter.adapters` entry points;
- discovery metadata never grants execution authority;
- provider credentials stay in trusted runtime bindings, not `ToolSpec`;
- nested/array result fields must preserve record alignment.

See [Adapter authoring](https://jdeun.github.io/SchemaRouter/adapter-authoring/) and
[Third-party adapter plugins](https://jdeun.github.io/SchemaRouter/guides/adapter-plugins/).

### Decision backend/plugin

Use this for bounded model/heuristic decisions over a finite local option set.

- reusable third-party backends use the `schemarouter.decision_backends` entry-point group;
- provider output is a signal, not authority;
- new backends must reject invalid option IDs/confidence values and preserve local abstention rules;
- wire compatibility is not benchmark evidence.

See [Decision backend plugins](https://jdeun.github.io/SchemaRouter/integrations/decision-backend-plugins/)
and [Decision-model ecosystem](https://jdeun.github.io/SchemaRouter/integrations/decision-model-ecosystem/).

### Framework bridge

Use this when another ecosystem needs to import or export SchemaRouter capabilities.

- integrations live under `schemarouter.integrations`;
- dependencies must remain optional/lazily imported;
- core SchemaRouter must import without the extra;
- execution must continue through SchemaRouter policy, schema validation, fingerprint checks, and
  trusted bindings;
- do not duplicate the external framework's graph, memory, or agent runtime.

LangChain/LangGraph and LlamaIndex are the reference patterns.

### Trusted local SDK/client binding

If a provider already has a good Python SDK but no portable schema protocol, prefer an explicit
`ToolSpec` plus trusted bound invoker rather than adding a fake network adapter. The capability
contract and execution authority remain separate.

## Design rules

Changes must preserve these principles:

1. remote metadata describes capability but never grants execution authority;
2. model output is untrusted until projected onto registered schemas;
3. credentials remain outside model-visible arguments and persisted contracts;
4. schema and invoker drift fail closed;
5. raw input/output values are validated before crossing the trusted execution boundary;
6. mutations, destructive calls, and ambiguous remote side effects require local policy;
7. observability must not expose payloads by default;
8. integrations must call through SchemaRouter execution rather than bypassing it;
9. installed adapter plugins must never be auto-imported from discovery alone;
10. approval and execution-budget failures must remain fail-closed.

## Backwards compatibility

SchemaRouter is Beta / pre-1.0, but compatibility changes are still deliberate.

- patch releases should remain backward-compatible except where preserving behavior violates a
  security/correctness fail-closed invariant;
- minor releases may make documented breaking changes;
- documented public APIs should normally receive a deprecation period before removal;
- persisted storage changes require explicit version/migration handling;
- breaking changes require changelog + migration guidance.

See [Versioning and compatibility](https://jdeun.github.io/SchemaRouter/versioning/).

## Research boundary

Product code and frozen research evidence are related but are not the same release surface.

Do **not** silently change a frozen corpus, split, benchmark condition, promotion gate, or evidence
interpretation to make a result look better. Research changes must preserve:

- exact workload identity;
- run/model/runtime metadata;
- machine-readable outputs;
- negative/null results;
- preregistered thresholds where applicable;
- the distinction between controlled evidence and general production claims.

If a product fix changes benchmark semantics, document the change and run a new explicitly versioned
experiment rather than rewriting historical evidence.

See [Research governance](https://jdeun.github.io/SchemaRouter/research/governance/) and the
[research evidence package](https://jdeun.github.io/SchemaRouter/research/paper-evidence-package/).

## Pull requests

A change is not complete until the relevant items are true:

- tests cover public behavior and adversarial failure cases;
- warnings remain clean;
- supported Python versions and Windows smoke remain compatible;
- Pyright and the 84% branch-coverage floor pass;
- minimum declared runtime dependencies remain usable;
- wheel/sdist clean-install smokes remain valid;
- public behavior is documented;
- optional dependencies stay behind extras;
- breaking API changes include changelog and migration guidance;
- benchmark claims point to reproducible evidence rather than prose-only assertions.

Use the repository pull-request template. Keep PRs single-purpose; unrelated cleanup should be a
separate change.

## Good first issues and help wanted

Maintainers should use `good first issue` only when the task has:

- a bounded file/module surface;
- a reproducible acceptance criterion;
- no hidden credentials or private infrastructure;
- no unresolved architecture decision;
- a reviewer who can explain the relevant contract publicly.

Use `help wanted` for larger but still externally tractable work. Research promotion decisions,
security incidents, release signing/credentials, and unresolved authority-model changes are not good
first issues.

The [public roadmap](https://jdeun.github.io/SchemaRouter/project/roadmap/) separates stable product,
research, integrations, and community work so contributors can avoid accidentally reopening frozen
boundaries.

## Acknowledgement and release notes

Merged contributors are credited through Git history and the pull request. In addition:

- externally visible behavior changes belong in the changelog/release notes;
- a release note should link the PR/issue when the context helps users migrate or verify behavior;
- benchmark/evidence contributions retain author/source attribution in their artifact or evidence
  record where technically available;
- logos, employer names, testimonials, and "used by" claims require explicit permission;
- contribution credit never depends on promotional activity or starring the repository.

## Community channels and GitHub Discussions

**Current decision: do not enable GitHub Discussions yet.**

At the current adoption stage, Issues provide a clearer bounded work queue and avoid splitting usage
questions across low-volume channels. Revisit Discussions when external usage produces recurring
Q&A or design conversation that does not belong in actionable issues.

If enabled later, start with only:

1. **Q&A** — usage/integration questions;
2. **Ideas** — pre-issue design proposals;
3. **Show and tell** — downstream integrations and reproductions;
4. **Announcements** — maintainer-only release/project updates.

Security reports must remain private regardless of community channel.

## Brand changes

Production brand assets live under `docs/assets/brand/`. Treat the SVG files as the source of truth.

Brand changes should preserve the brace + routing-hub concept, graphite/teal palette, light/dark
contrast, and compact-mark legibility. Do not replace production SVGs with raster-only generated
artwork.

See the [brand guide](https://jdeun.github.io/SchemaRouter/project/brand/).

## Release process

Contributors do not need release credentials. The protected release workflow owns build provenance,
SBOM generation, GitHub artifact attestations, PyPI Trusted Publishing, and post-publish digest
verification.

See:

- [Release checklist](https://jdeun.github.io/SchemaRouter/release-checklist/)
- [Trust, stability, and public evidence](https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/)

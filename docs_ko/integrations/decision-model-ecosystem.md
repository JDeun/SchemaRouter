# Decision-model ecosystem intake

이 페이지는 model quality가 아니라 **integration shape**을 추적합니다. A listed project is not endorsed or
promoted merely because SchemaRouter can connect to it.

Last reviewed: **2026-09-28**.

The machine-readable discovery/benchmark intake state lives in
`benchmarks/system-one-candidate-registry.json`. Keep model discovery there instead of hard-coding
candidate names into planner logic.

The promotion target itself is centralized separately in
`benchmarks/operation-routing-production-targets.json`. The registry mirrors that target for
discovery UX, and tests reject drift between the two files.

## Intake 규칙

Choose the narrowest stable boundary that fits a new model/runtime:

| Integration shape | SchemaRouter path | Core change normally needed? |
|---|---|---:|
| Jev/System One-compatible HTTP API | `SystemOneDecisionBackend` | No |
| Direct official Laya Python runtime | `LayaDecisionBackend` | No |
| One-off Python experiment | `CallableDecisionBackend` / `--decision-callable` | No |
| Reusable non-System-One Python runtime | `schemarouter.decision_backends` plugin | No |
| New semantic primitive that does not fit `DecisionBackend` | research-only adapter first | Maybe, after evidence |

## Current discovery matrix

The ecosystem changes quickly. Pin exact repository/model/runtime revisions before any benchmark.

### Jev / TypeSafe

- hosted reference System One API;
- existing SchemaRouter integration: `JevDecisionBackend`;
- generic compatible path: `SystemOneDecisionBackend`;
- credentialed comparison only; never a CI requirement.

### Laya

- open typed-decision model family;
- direct Python path: `LayaDecisionBackend`;
- supports typed `choice`, `score`, and `noul` primitives in its native runtime;
- community HTTP/ONNX runtimes can use the generic System One path when they preserve the compatible
  contract.

Research status is tracked separately. The current v4 evidence rejects the tested direct
full-catalog Laya choice configuration and the pinned winner-only native `noul` veto, but those
results do not imply every Laya checkpoint/runtime/primitive has the same behavior.

### Kev

Repository family: `jaredpalmer/kev`.

- Jev/System One-compatible `/v1/systemone` server;
- open model sizes include 0.8B, 4B, 9B, and 27B classes;
- supports `choice`, `noul`, and `score`;
- SchemaRouter path: `SystemOneDecisionBackend`;
- model size/revision is a benchmark variable, not an integration-code variable;
- current SchemaRouter research: pinned Kev-0.8B `choice+noul` #299 / PR #300 is the active
  1,800-row v4 screen.

### Mapika decider

Repository: `Mapika/decider`.

- Jev/System One-compatible runtime family;
- SchemaRouter path: `SystemOneDecisionBackend`;
- candidate model/runtime revision must be pinned independently before benchmark;
- no SchemaRouter quality result yet.

### Decis

Repository: `chaitin/Decis`.

- self-hosted Jev-compatible server;
- presents multiple engines behind one `/v1/systemone` endpoint;
- currently includes Laya and Kev engine paths;
- SchemaRouter path: `SystemOneDecisionBackend`.

This is an example of why SchemaRouter should target the wire contract instead of adding one class
per underlying model.

### LiteVar System One

Repository: `LiteVar/system-one`.

- local-first cross-platform System One runtime;
- Jev-compatible API;
- model-independent runtime abstraction with Laya as an initial backend;
- SchemaRouter path: `SystemOneDecisionBackend`.

### laya-serve

Repository: `stiermid/laya-serve`.

- Jev-compatible HTTP serving layer for Laya;
- SchemaRouter path: `SystemOneDecisionBackend`;
- use direct `LayaDecisionBackend` instead when an application wants the Python runtime in-process.

### OpenJev variants

Multiple unrelated projects use the OpenJev name. Treat each repository/runtime as a distinct
provider and pin it explicitly.

The currently tracked discovery entry is `SiliconLabAI/OpenJev`.

Its source repository is MIT at the observed discovery revision, but backend/model licensing must
still be checked independently for the exact selected runtime. Use `SystemOneDecisionBackend` only
when a selected backend actually preserves the compatible wire contract. Otherwise use a decision
plugin/callable.

### AnyJev

Repository: `nokia-applied-research/AnyJev`.

- converts causal LLMs into typed-decision/readout variants;
- runtime/readout support differs by level/model;
- SchemaRouter path: third-party `schemarouter.decision_backends` plugin or research callable
  unless/until a stable System One-compatible server contract is pinned;
- current SchemaRouter state: #311 / PR #313 stages a zero-label L0 content-free `noul` veto
  behind the immutable BGE winner;
- the research workflow remains dormant until explicitly activated by the guarded marker/manual
  path, and the marker is forbidden until all preregistered Kev-based candidates are non-promotable.

### Bespoke Nimble

Repository: `bespokelabsai/nimble`.

- typed candidate-scoring model/runtime rather than a Jev-wire-compatible server;
- model/checkpoint calibration is release-specific and must be pinned with the selected runtime;
- the current Bespoke-Nimble-9B model card reports Apache-2.0, while the observed GitHub code
  repository has no root LICENSE; verify code and model licensing separately for the selected release;
- SchemaRouter path: plugin or research callable;
- larger memory/GPU requirements make it a separate runtime experiment rather than a drop-in CPU
  comparison;
- no SchemaRouter quality result yet.

### System One Open

Repository: `mithalouni/system-one-open`.

- open Jev-style typed-decision implementation with a distinct serving/runtime contract;
- SchemaRouter path: plugin or research callable unless a compatible wire endpoint is explicitly
  verified;
- pin weights/runtime independently before treating a hosted demo endpoint as reproducible evidence;
- no SchemaRouter quality result yet.

### Other model families and runtimes

Projects such as alternative Laya ONNX/TypeScript runtimes, decision heads, distilled decision
models, or future typed-decision engines should enter through the same intake rule rather than
receiving a permanent SchemaRouter core class by default.

## Promotion workflow for a new model

Compatibility and model promotion stay separate:

1. pin repository/runtime/model revisions; observed registry revisions are discovery provenance only;
2. connect through System One, plugin, or callable without changing planning authority;
3. run the frozen benchmark protocol;
4. record exact-route, unsupported rejection, false-route rate, latency, errors, and authority
   violations;
5. freeze semantics before any fresh-surface confirmation;
6. only promote a default/recommended profile when independent evidence passes the active quality
   gate.

## Authority invariant

No integration path changes the core rule:

> A model may score, select from, or veto finite locally authorized choices, but it may not create
> tools, endpoints, fields, arguments, policy, or execution authority.

This rule applies equally to hosted Jev, Laya, Kev, OpenJev, AnyJev, and future models.

# Decision-model ecosystem intake

This page tracks **integration shape**, not model quality. A listed project is not endorsed or
promoted merely because SchemaRouter can connect to it.

Last reviewed: **2026-09-28**.

## Intake rule

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

Research status is tracked separately. A failed routing configuration does not imply every Laya
checkpoint/runtime/primitive has the same result.

### Kev

Repository family: `jaredpalmer/kev`.

- Jev/System One-compatible `/v1/systemone` server;
- open model sizes include 0.8B, 4B, 9B, and 27B classes;
- supports `choice`, `noul`, and `score`;
- SchemaRouter path: `SystemOneDecisionBackend`;
- model size/revision is a benchmark variable, not an integration-code variable.

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

Examples observed in current discovery include:
- `lookski/openjev`: local causal-LM masked-logit System One-style engine;
- `razorback16/openjev`: Jev-compatible server exposing several decision-model backends.

Use `SystemOneDecisionBackend` only when the selected runtime actually preserves the compatible
wire contract. Otherwise use a decision plugin/callable.

### AnyJev

Repository: `nokia-applied-research/AnyJev`.

- converts causal LLMs into typed-decision/readout variants;
- runtime/readout support differs by level/model;
- SchemaRouter path: third-party `schemarouter.decision_backends` plugin or research callable
  unless/until a stable System One-compatible server contract is pinned.

### Other model families and runtimes

Projects such as alternative Laya ONNX/TypeScript runtimes, decision heads, distilled decision
models, or future typed-decision engines should enter through the same intake rule rather than
receiving a permanent SchemaRouter core class by default.

## Promotion workflow for a new model

Compatibility and model promotion are deliberately separate:

1. pin repository/runtime/model revisions;
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

# Security policy

SchemaRouter treats remote schemas, model output, and tool descriptions as untrusted data. Trusted
local application code remains the authority for credentials, side effects, bindings, and policy.

## Supported versions

SchemaRouter is currently pre-1.0. Security fixes are applied to the latest non-prerelease release
line and the current development line. Older 0.x lines are not guaranteed to receive backports unless
a release-specific support window is announced.

## Reporting a vulnerability

Do not include credentials, tokens, private endpoints, or exploit details in a public issue.

Use GitHub private vulnerability reporting for this repository when it is available. If private
reporting is not available, contact the repository owner privately through GitHub before publishing
technical details.

For non-sensitive correctness bugs, normal GitHub issues are appropriate.

## Threat model

### Remote schema and model output

OpenAPI documents, MCP metadata, human-readable documentation, and LLM-produced analyses are not
execution authority.

SchemaRouter:

- projects model output back onto the registered schema;
- rejects undeclared tools, endpoints, parameters, and fields;
- validates input and raw output with JSON Schema;
- rejects stale schema fingerprints and stale invoker bindings;
- requires trusted local policy for mutation, destructive, or unclassified remote operations.

### Credentials

Runtime credentials must remain outside model-visible tool arguments.

OpenAPI schema-fetch headers and runtime API headers use separate channels. Sensitive headers such as
Authorization, Cookie, Host, and proxy authorization cannot be supplied through model-selected
arguments.

Do not embed credentials in schema, documentation, or API URLs.

Authenticated MCP follows the same rule. Bearer/custom headers live in the trusted transport layer,
and MCP URLs containing userinfo credentials are rejected. Protocol-controlled `Mcp-*` headers
cannot be overridden through SchemaRouter's trusted-header channel. Custom OAuth, mTLS, proxy, or
gateway behavior belongs behind an application-supplied `MCPClientFactory`.

### Network destinations and SSRF

SchemaRouter supports localhost and private-network MCP/OpenAPI endpoints because local
developer tools are a primary use case, so it does not globally deny private or link-local
addresses.

`SchemaRouter.from_url()` and `inspect_url()` must be treated as network-capable APIs.

If an application accepts URLs from untrusted end users, the application must apply its own network
policy before passing those URLs to SchemaRouter. A hosted service should normally:

- allowlist approved hosts or service registries;
- resolve and reject cloud metadata, loopback, link-local, and private ranges unless explicitly
  required;
- account for DNS rebinding in its network layer;
- use egress controls where possible.

SchemaRouter restricts schema/document redirects to the original origin and restricts OpenAPI
runtime calls to an explicitly approved origin. OpenAPI runtime responses are streamed through a
bounded reader with a 16 MiB default limit, matching the bounded-response posture used by the
OPTIMADE adapter.

Cross-document OpenAPI `$ref` fetching is disabled by default. When trusted application code opts
in, referenced documents must stay on the entry document's origin, schema headers are reused only
within that origin, redirects remain same-origin, and depth/document/aggregate-byte limits apply.
Documents using `$id` base-URI rebasing or non-JSON-Pointer anchors fail closed in the current
resolver rather than being guessed.

These checks do not replace an application's initial URL admission policy.

### Observability

Run-event arguments and result payloads are redacted by default.

`RunConfig(include_payloads=True)` may expose user data, API responses, identifiers, or other
sensitive information to the direct event consumer. Enable payload tracing only when the destination
is trusted and appropriate retention controls exist.

The optional OpenTelemetry exporter is stricter: it exports structural attributes but
does not export argument values, result payloads, RunConfig metadata, tags, or exception messages,
even when the underlying event stream opted into payloads.

Persistent run traces store the exact `RunEvent` envelope they receive. With the default runtime
configuration, argument values and result payloads remain redacted. If
`RunConfig(include_payloads=True)` is used, those values may be written to disk and become subject
to the application's access-control, encryption-at-rest, backup, and retention policy. SchemaRouter
does not encrypt the SQLite trace database.

### Approval, budgets, and retries

Local execution policy is the first side-effect gate. Applications can additionally require a
trusted sync/async approval callback for non-read-only or all calls. Missing callbacks, negative
decisions, and callback failures deny execution.

Per-run budgets bound logical calls, total attempts, remote attempts, elapsed time, per-tool calls,
and application-defined cost units. Retry attempts consume attempt/remote/cost budgets before the
invoker runs, and retry backoff is capped by the remaining elapsed-time budget. Async approval
callbacks and execution hooks are also bounded by the remaining elapsed time; synchronous trusted
callbacks are checked immediately after they return. Budget refusals and schema contract violations
are never retried.

Automatic retries remain limited to endpoints classified as read-only unless trusted local code
explicitly opts into retrying non-read-only operations. Built-in OpenAPI and OPTIMADE HTTP invokers
retry only a conservative transient-status set and fail fast on other HTTP errors plus deterministic
response-contract failures. Trusted custom invokers can raise `NonRetryableInvocationError` to
prevent retrying a failure that cannot safely recover.

### Trusted execution hooks

Before/after execution hooks are trusted local executable code. They are not redacted telemetry.
Before hooks can observe validated argument values; after hooks can observe the final projected
result payload. Do not attach remote or third-party callbacks unless they are trusted for that data.

Hooks receive detached model snapshots and cannot mutate the executable call or returned result.
Non-None hook returns are rejected. Hook exceptions fail closed, and after-hook failures are not
classified as retryable tool failures, preventing an observability/middleware outage from repeating
an already successful invocation.

### Trusted contract amendment

`SchemaRouter.amend_capability()` is trusted local code at the same grade as
binding an invoker. It is not reachable from remote content, model output, or a
decision backend.

It can only declare or annotate result semantics. Execution identity and
validation shape are refused, so an amendment cannot redirect a call, widen the
input surface, reclassify a destructive operation as read-only, or relax the
validation of a response the source declared. A refused amendment registers
nothing and leaves the binding untouched.

`metadata` is refused too, on either the tool or an endpoint, even though it
looks like free-form annotation: validation can derive requirements from it
(`endpoint.metadata["output_required"]` shapes the synthesized output schema
when a source published no `output_schema`), so a metadata-only amendment
could otherwise change what a response must contain without touching a listed
aspect or the fingerprint.

Fingerprints still change on amendment, so stale-binding and stale-plan
protection are unchanged.

### Third-party adapter plugins

Installed entry points are local executable code. SchemaRouter can inspect plugin metadata without
importing it, but never auto-loads discovered plugins. Actual import requires an explicit non-empty
allowlist supplied by trusted application code. Remote content and model output cannot select an
installed plugin to import.

### Third-party decision-backend plugins

Decision-backend entry points are also trusted local executable code. Discovery reads only package
metadata; no plugin module is imported until trusted application code requests one exact plugin
name. Duplicate names fail before import so package-install order cannot silently choose an
implementation.

A loaded decision backend still receives only the finite option set created by SchemaRouter.
Unknown option IDs, duplicate selections, malformed results, and invalid scores fail closed through
the normal `DecisionBackend` validation path. Plugin code itself is trusted Python code and may
perform arbitrary local actions, so applications must treat plugin installation/loading as a code
trust decision rather than as model output.

Shared benchmark configuration is passed explicitly from a selected environment variable. Reports
record plugin identity, distribution/version, the configuration environment-variable name, and
configuration keys only; configuration values are not persisted.

### Human-readable documentation

Documentation-derived schemas remain non-executable proposals until grounding and explicit approval
succeed. Documentation text is treated as untrusted and script/style content is removed before model
analysis.

## Security-sensitive contribution rules

Changes affecting any of the following require adversarial regression tests:

- authorization or credentials;
- URL/redirect/origin handling;
- schema fingerprints or registry mutation;
- execution policy;
- retries or side effects;
- input/output validation;
- event payload redaction and telemetry export;
- adapter plugin loading;
- decision-backend plugin discovery/loading and benchmark secret handling;
- MCP authenticated/custom transports;
- per-call approval or execution budgets;
- trusted execution hooks;
- documentation grounding or proposal approval.

See also:

- [Architecture](../architecture.md)
- [Adapter authoring](../adapter-authoring.md)
- [Release checklist](../release-checklist.md)

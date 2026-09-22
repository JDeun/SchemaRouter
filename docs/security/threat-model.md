# Security policy

SchemaRouter treats remote schemas, model output, and tool descriptions as untrusted data. Trusted
local application code remains the authority for credentials, side effects, bindings, and policy.

## Supported versions

SchemaRouter is currently pre-1.0. Security fixes are applied to the latest development/release line.
Once non-alpha releases are published, supported release lines will be listed here explicitly.

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

SchemaRouter therefore:

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

SchemaRouter intentionally supports localhost and private-network MCP/OpenAPI endpoints because local
developer tools are a primary use case. Therefore it does not globally deny private or link-local
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
OPTIMADE adapter. These checks do not replace an application's initial URL admission policy.

### Observability

Run-event arguments and result payloads are redacted by default.

`RunConfig(include_payloads=True)` may expose user data, API responses, identifiers, or other
sensitive information to the direct event consumer. Enable payload tracing only when the destination
is trusted and appropriate retention controls exist.

The optional OpenTelemetry exporter is intentionally stricter: it exports structural attributes but
does not export argument values, result payloads, RunConfig metadata, tags, or exception messages,
even when the underlying event stream opted into payloads.

Persistent run traces store the exact `RunEvent` envelope they receive. With the default runtime
configuration, argument values and result payloads remain redacted. If
`RunConfig(include_payloads=True)` is used, those values may be written to disk and become subject
to the application's access-control, encryption-at-rest, backup, and retention policy. SchemaRouter
does not encrypt the SQLite trace database.

### Approval, budgets, and retries

Local execution policy remains the first side-effect gate. Applications can additionally require a
trusted sync/async approval callback for non-read-only or all calls. Missing callbacks, negative
decisions, and callback failures deny execution.

Per-run budgets bound logical calls, total attempts, remote attempts, elapsed time, per-tool calls,
and application-defined cost units. Retry attempts consume attempt/remote/cost budgets before the
invoker runs. Budget refusals and schema contract violations are never retried.

Automatic retries remain limited to endpoints classified as read-only unless trusted local code
explicitly opts into retrying non-read-only operations.

### Third-party adapter plugins

Installed entry points are local executable code. SchemaRouter can inspect plugin metadata without
importing it, but never auto-loads discovered plugins. Actual import requires an explicit non-empty
allowlist supplied by trusted application code. Remote content and model output cannot select an
installed plugin to import.

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
- MCP authenticated/custom transports;
- per-call approval or execution budgets;
- documentation grounding or proposal approval.

See also:

- [Architecture](../architecture.md)
- [Adapter authoring](../adapter-authoring.md)
- [Release checklist](../release-checklist.md)

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

Authenticated MCP keeps bearer/custom headers inside the trusted transport boundary. MCP URLs with
embedded userinfo credentials are rejected, protocol-controlled `Mcp-*` headers cannot be
overridden through trusted headers, and OAuth/mTLS/proxy/gateway behavior should be implemented
behind a trusted application-supplied `MCPClientFactory`.

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

The optional OpenTelemetry exporter is stricter than the direct event stream: it exports structural
attributes but does not export argument values, result payloads, RunConfig metadata, tags, or
exception messages, even when the source event stream opted into payloads.

### Approval, budgets, and retries

Applications may require a trusted sync/async approval callback for non-read-only calls or for every
call. Missing callbacks, denied decisions, and callback exceptions fail closed.

Per-run execution budgets can bound logical tool calls, invoker attempts, remote attempts, elapsed
time, per-tool call counts, and application-defined cost units. Retry attempts consume attempt,
remote, and cost budgets before invocation. Budget refusals and schema contract violations are never
retried.

Automatic retries remain limited to endpoints classified as read-only unless trusted local code
explicitly opts into retrying non-read-only operations.

### Third-party adapter plugins

Installed adapter entry points are executable local Python code. SchemaRouter can discover their
metadata without importing them, but actual loading requires a non-empty explicit allowlist supplied
by trusted application code. Remote schemas and model output cannot choose installed plugins to
import.

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
- adapter plugin discovery/loading;
- authenticated/custom MCP transports;
- per-call approval or execution budgets;
- documentation grounding or proposal approval.

See also:

- [Architecture](docs/architecture.md)
- [Adapter authoring](docs/adapter-authoring.md)
- [Release checklist](docs/release-checklist.md)

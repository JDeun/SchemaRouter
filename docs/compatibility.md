# Compatibility testing

SchemaRouter separates deterministic release gates from external-service smoke tests.

## Required CI

Every pull request runs:

- Python 3.10 / 3.11 / 3.12 core tests;
- warnings-as-errors;
- executable quickstart;
- wheel and sdist build + metadata checks;
- optional LangChain integration;
- real MCP Streamable HTTP integration using the official SDK and a local HTTP server.

These tests are deterministic and are release blockers.

## Live OpenAPI smoke

The `Compatibility Smoke` workflow runs weekly and can also be triggered manually. It imports and
executes against the public Swagger Petstore OpenAPI endpoint.

This specifically exercises a common real-world pattern:

- relative OpenAPI `servers` URL;
- query parameter enum;
- read-only remote execution;
- array response;
- nested local `#/components/...` references;
- runtime output validation.

The default source is:

```text
https://petstore3.swagger.io/api/v3/openapi.json
```

Set `SCHEMAROUTER_LIVE_OPENAPI_URL` when running the smoke script locally to use another compatible
service.

External smoke failures are compatibility signals, not pull-request blockers, because third-party
availability is outside SchemaRouter's control.

## Release interpretation

A green required CI proves package and protocol behavior under controlled conditions. A recent green
live smoke provides additional evidence that the OpenAPI adapter remains compatible with a real
public service. Both should be reviewed before a release candidate is promoted.
